"""Verify a point cloud against the control measurements.

Workflow: pick the marker points in CloudCompare (or any viewer that shows coordinates),
save them as a small CSV, and let this module compare the distances between them with the
distances you measured by laser. That comparison is the only thing that turns "a scan" into
"a survey": it produces a scale factor and a per-measurement deviation you can publish.
"""

from __future__ import annotations

import csv
import math
from dataclasses import dataclass
from pathlib import Path

from scan2bim.control import ControlDistance, ControlFile

# A tolerance expressed purely as a percentage assumes the error grows with length, which is
# the very hypothesis being tested, and it is brutally tight on short lines. Survey instruments
# are specified as a fixed part plus a proportional part; so is this.
DEFAULT_TOLERANCE_MM = 25.0
DEFAULT_TOLERANCE_PCT = 0.5

# Only advise rescaling when the estimated scale error clears this many standard errors. With
# four to six distances the estimator's own noise is large, and a naive threshold fires on a
# perfect cloud.
RESCALE_SIGMA = 3.0

# Markers taped on the storey datum line share one true height, so the spread of their picked
# z values measures the cloud's tilt. Beyond this it is not a rounding artefact.
LEVEL_SPREAD_NOTE_MM = 20.0


@dataclass(frozen=True)
class Marker:
    name: str
    x_mm: float
    y_mm: float
    z_mm: float

    def distance_mm(self, other: Marker) -> float:
        return math.dist((self.x_mm, self.y_mm, self.z_mm), (other.x_mm, other.y_mm, other.z_mm))


@dataclass(frozen=True)
class Comparison:
    distance_id: str
    measured_mm: float
    cloud_mm: float
    scan: str | None = None

    @property
    def deviation_mm(self) -> float:
        return self.cloud_mm - self.measured_mm

    @property
    def deviation_pct(self) -> float:
        return 100.0 * self.deviation_mm / self.measured_mm if self.measured_mm else math.inf


@dataclass(frozen=True)
class Verification:
    comparisons: list[Comparison]
    missing_markers: list[str]
    tolerance_pct: float = DEFAULT_TOLERANCE_PCT
    tolerance_mm: float = DEFAULT_TOLERANCE_MM
    level_spread_mm: float | None = None

    @property
    def scale_factor(self) -> float:
        """Least squares factor s minimising the residual of s * cloud - measured."""
        numerator = sum(c.cloud_mm * c.measured_mm for c in self.comparisons)
        denominator = sum(c.cloud_mm**2 for c in self.comparisons)
        return numerator / denominator if denominator else math.nan

    def by_scan(self) -> dict[str, list[Comparison]]:
        """Comparisons grouped by the capture their markers came from."""
        grouped: dict[str, list[Comparison]] = {}
        for comparison in self.comparisons:
            grouped.setdefault(comparison.scan or "unlabelled", []).append(comparison)
        return grouped

    def allowance_mm(self, length_mm: float) -> float:
        return self.tolerance_mm + self.tolerance_pct / 100.0 * length_mm

    def within_tolerance(self, comparison: Comparison) -> bool:
        return abs(comparison.deviation_mm) <= self.allowance_mm(comparison.measured_mm)

    @property
    def max_abs_deviation_pct(self) -> float:
        return max((abs(c.deviation_pct) for c in self.comparisons), default=math.nan)

    @property
    def scale_standard_error(self) -> float:
        """Standard error of the fitted scale factor.

        Without this the factor is a number with no meaning: with four to six distances and
        realistic picking noise, a perfect cloud still yields a scale factor a few tenths of a
        percent away from one.
        """
        n = len(self.comparisons)
        if n < 2:
            return math.nan
        s = self.scale_factor
        residuals = [c.measured_mm - s * c.cloud_mm for c in self.comparisons]
        variance = sum(r**2 for r in residuals) / (n - 1)
        denominator = sum(c.cloud_mm**2 for c in self.comparisons)
        return math.sqrt(variance / denominator) if denominator else math.nan

    @property
    def residual_rms_mm(self) -> float:
        """RMS of what is left after the best scale is applied: the part scaling cannot fix."""
        if not self.comparisons:
            return math.nan
        s = self.scale_factor
        return math.sqrt(
            sum((c.measured_mm - s * c.cloud_mm) ** 2 for c in self.comparisons)
            / len(self.comparisons)
        )

    @property
    def scale_is_significant(self) -> bool:
        error = self.scale_standard_error
        if math.isnan(error):
            return False
        if error == 0:
            # A perfect fit means every distance agrees on the same factor: as certain as it
            # gets, so any departure from 1 is real.
            return abs(self.scale_factor - 1.0) > 1e-9
        return abs(self.scale_factor - 1.0) > RESCALE_SIGMA * error

    @property
    def rms_deviation_mm(self) -> float:
        if not self.comparisons:
            return math.nan
        return math.sqrt(sum(c.deviation_mm**2 for c in self.comparisons) / len(self.comparisons))

    @property
    def passed(self) -> bool:
        if not self.comparisons or self.missing_markers:
            return False
        return all(self.within_tolerance(c) for c in self.comparisons)

    @property
    def advice(self) -> str:
        if self.missing_markers:
            return (
                "Markers missing from the picked file: "
                + ", ".join(sorted(set(self.missing_markers)))
                + ". Pick them or drop those control distances."
            )
        if not self.comparisons:
            return "Nothing to compare. Add control distances and pick their markers."
        scale_error_pct = abs(self.scale_factor - 1.0) * 100
        if not self.passed:
            over = [c for c in self.comparisons if not self.within_tolerance(c)]
            names = ", ".join(c.distance_id for c in over)
            return (
                f"Outside tolerance: {names}. Rescan that area, or use the cloud only as a "
                "shape reference there and take those dimensions from the control list."
            )
        if self.scale_is_significant:
            return (
                f"Within tolerance, but the cloud is systematically off by "
                f"{scale_error_pct:.2f}% (scale {self.scale_factor:.4f} "
                f"+/- {self.scale_standard_error * 100:.2f}%). Scaling is worth doing "
                "(CloudCompare: Edit > Multiply/Scale). Note that scaling only corrects a "
                "uniform error; drift that varies across the building will remain."
            )
        return (
            "Within tolerance, and the apparent scale error is inside the noise of the "
            "estimate itself, so do not rescale. Model on this cloud."
        )


def read_markers(path: Path, *, units: str = "m") -> dict[str, Marker]:
    """Read `name,x,y,z` rows. A header line is optional and detected automatically.

    All coordinates must come from one registered cloud. Picking marker A in one room scan and
    marker B in another, with the two never aligned, produces a distance between two unrelated
    coordinate systems: a number that looks fine and means nothing.
    """
    factor = {"m": 1000.0, "mm": 1.0, "cm": 10.0}.get(units)
    if factor is None:
        raise ValueError(f"Unknown units {units!r}, expected m, cm or mm")

    markers: dict[str, Marker] = {}
    with path.open(newline="", encoding="utf-8") as handle:
        for row in csv.reader(handle):
            if len(row) < 4:
                continue
            name = row[0].strip()
            try:
                x, y, z = (float(value) * factor for value in row[1:4])
            except ValueError:
                continue  # header or comment line
            if name in markers:
                raise ValueError(
                    f"Marker {name!r} appears twice in {path}. Picking the same marker in two "
                    "different scans is the mistake this would hide, so fix the file rather "
                    "than letting one silently win."
                )
            markers[name] = Marker(name=name, x_mm=x, y_mm=y, z_mm=z)
    if not markers:
        raise ValueError(f"No marker rows found in {path}. Expected: name,x,y,z")
    return markers


def level_spread_mm(control: ControlFile, markers: dict[str, Marker]) -> float | None:
    """Height spread of the markers taped on the storey datum line.

    Distances between points are invariant under rotation, so no amount of distance checking
    reveals a cloud that is tilted relative to gravity. Markers set out on one horizontal line
    do: their true heights are equal, so whatever spread the cloud reports is its levelling
    error. Revit levels are horizontal planes, which is why this matters.
    """
    picked = [markers[name].z_mm for name in control.metre_line_markers if name in markers]
    if len(picked) < 2:
        return None
    return max(picked) - min(picked)


def compare(
    control: ControlFile,
    markers: dict[str, Marker],
    *,
    tolerance_pct: float = DEFAULT_TOLERANCE_PCT,
    tolerance_mm: float = DEFAULT_TOLERANCE_MM,
) -> Verification:
    comparisons: list[Comparison] = []
    missing: list[str] = []
    for distance in control.control_distances:
        pair = _lookup(distance, markers, missing)
        if pair is None:
            continue
        start, end = pair
        comparisons.append(
            Comparison(
                distance_id=distance.id,
                measured_mm=distance.length_mm,
                cloud_mm=start.distance_mm(end),
                scan=distance.scan,
            )
        )
    return Verification(
        comparisons=comparisons,
        missing_markers=missing,
        tolerance_pct=tolerance_pct,
        tolerance_mm=tolerance_mm,
        level_spread_mm=level_spread_mm(control, markers),
    )


def _lookup(
    distance: ControlDistance, markers: dict[str, Marker], missing: list[str]
) -> tuple[Marker, Marker] | None:
    start = markers.get(distance.from_marker)
    end = markers.get(distance.to_marker)
    if start is None:
        missing.append(distance.from_marker)
    if end is None:
        missing.append(distance.to_marker)
    if start is None or end is None:
        return None
    return start, end
