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

DEFAULT_TOLERANCE_PCT = 1.0

# Below this the scale error is not worth chasing; above it, rescale the cloud before modelling.
RESCALE_ADVICE_PCT = 0.3


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
    tolerance_pct: float

    @property
    def scale_factor(self) -> float:
        """Least squares factor s minimising the residual of s * cloud - measured."""
        numerator = sum(c.cloud_mm * c.measured_mm for c in self.comparisons)
        denominator = sum(c.cloud_mm**2 for c in self.comparisons)
        return numerator / denominator if denominator else math.nan

    @property
    def max_abs_deviation_pct(self) -> float:
        return max((abs(c.deviation_pct) for c in self.comparisons), default=math.nan)

    @property
    def rms_deviation_mm(self) -> float:
        if not self.comparisons:
            return math.nan
        return math.sqrt(sum(c.deviation_mm**2 for c in self.comparisons) / len(self.comparisons))

    @property
    def passed(self) -> bool:
        if not self.comparisons or self.missing_markers:
            return False
        return self.max_abs_deviation_pct <= self.tolerance_pct

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
            return (
                f"Largest deviation {self.max_abs_deviation_pct:.2f}% exceeds the "
                f"{self.tolerance_pct:.2f}% tolerance. Rescan the affected area, or use the "
                "cloud only as a shape reference and take dimensions from the control list."
            )
        if scale_error_pct > RESCALE_ADVICE_PCT:
            return (
                f"Within tolerance, but the cloud is systematically off by "
                f"{scale_error_pct:.2f}%. Scale it by {self.scale_factor:.5f} before modelling "
                "(CloudCompare: Edit > Multiply/Scale)."
            )
        return "Within tolerance and no systematic scale error. Model on this cloud."


def read_markers(path: Path, *, units: str = "m") -> dict[str, Marker]:
    """Read `name,x,y,z` rows. A header line is optional and detected automatically."""
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
            markers[name] = Marker(name=name, x_mm=x, y_mm=y, z_mm=z)
    if not markers:
        raise ValueError(f"No marker rows found in {path}. Expected: name,x,y,z")
    return markers


def compare(
    control: ControlFile,
    markers: dict[str, Marker],
    *,
    tolerance_pct: float = DEFAULT_TOLERANCE_PCT,
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
            )
        )
    return Verification(
        comparisons=comparisons, missing_markers=missing, tolerance_pct=tolerance_pct
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
