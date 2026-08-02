"""Control measurements: the hand-measured truth that outranks the point cloud.

A phone scan gives you shape. A laser distance meter gives you size. This module holds the
schema for those field measurements and the sanity checks that catch the mistakes people
actually make: a diagonal that was never taken, a wall thickness typed in centimetres, a
floor-to-floor height smaller than the floor-to-ceiling height.
"""

from __future__ import annotations

import math
from dataclasses import dataclass
from datetime import date, datetime
from pathlib import Path
from typing import Any, Literal

import yaml
from pydantic import BaseModel, Field, ValidationError, field_validator

Severity = Literal["ok", "warn", "fail"]

# An 1900s building is genuinely out of square. These thresholds do not mean "wrong", they
# mean "large enough that you must model it rather than straighten it".
OUT_OF_SQUARE_NOTE_MM = 30.0
STOREY_HEIGHT_SPREAD_NOTE_MM = 30.0
MIN_WALL_MM = 60.0
MAX_WALL_MM = 1000.0
MIN_ROOM_MM = 800.0


class StoreyHeight(BaseModel):
    storey: str
    location: str = Field(description="Where in the storey this was measured, e.g. 'hall, north'")
    floor_to_ceiling_mm: float
    floor_to_floor_mm: float | None = None


class Room(BaseModel):
    id: str
    storey: str
    width_mm: float
    length_mm: float
    diagonal_a_mm: float | None = None
    diagonal_b_mm: float | None = None


class Wall(BaseModel):
    id: str
    kind: Literal["exterior", "interior"]
    thickness_mm: float
    measured_at: str | None = Field(default=None, description="e.g. 'window reveal, south facade'")


class ControlDistance(BaseModel):
    """A long tape/laser shot between two physical markers, used to scale and check the cloud."""

    id: str
    from_marker: str
    to_marker: str
    length_mm: float
    storey: str | None = None
    description: str | None = None
    scan: str | None = Field(
        default=None,
        description=(
            "Which capture both markers appear in. Distances whose markers sit in separate, "
            "unregistered scans cannot be compared."
        ),
    )
    photo: str | None = Field(default=None, description="Photo of the measurement, in raw/photos/")


class ControlFile(BaseModel):
    project: str
    surveyed_on: str | None = None
    instrument: str | None = None
    storey_heights: list[StoreyHeight] = Field(default_factory=list)
    rooms: list[Room] = Field(default_factory=list)
    walls: list[Wall] = Field(default_factory=list)
    control_distances: list[ControlDistance] = Field(default_factory=list)
    metre_line_markers: list[str] = Field(
        default_factory=list,
        description=(
            "Markers taped on the storey datum line. Their true heights are equal, so the "
            "spread the cloud reports for them is its levelling error."
        ),
    )

    @field_validator("surveyed_on", mode="before")
    @classmethod
    def _accept_yaml_dates(cls, value: Any) -> Any:
        # YAML turns an unquoted 2026-11-03 into a date object; nobody should have to quote it.
        if isinstance(value, date | datetime):
            return value.isoformat()
        return value


@dataclass(frozen=True)
class Finding:
    severity: Severity
    code: str
    subject: str
    message: str

    def as_dict(self) -> dict[str, Any]:
        return {
            "severity": self.severity,
            "code": self.code,
            "subject": self.subject,
            "message": self.message,
        }


def load(path: Path) -> ControlFile:
    raw = yaml.safe_load(path.read_text(encoding="utf-8")) or {}
    try:
        return ControlFile.model_validate(raw)
    except ValidationError as exc:
        raise ValueError(f"{path} is not a valid control file:\n{exc}") from exc


def expected_diagonal_mm(width_mm: float, length_mm: float) -> float:
    return math.sqrt(width_mm**2 + length_mm**2)


def validate(control: ControlFile) -> list[Finding]:
    findings: list[Finding] = []
    findings += _check_duplicates(control)
    findings += _check_rooms(control)
    findings += _check_storey_heights(control)
    findings += _check_walls(control)
    findings += _check_control_distances(control)
    return findings


def worst(findings: list[Finding]) -> Severity:
    if any(f.severity == "fail" for f in findings):
        return "fail"
    if any(f.severity == "warn" for f in findings):
        return "warn"
    return "ok"


def _check_duplicates(control: ControlFile) -> list[Finding]:
    findings = []
    for label, ids in (
        ("room", [r.id for r in control.rooms]),
        ("wall", [w.id for w in control.walls]),
        ("control distance", [d.id for d in control.control_distances]),
    ):
        seen: set[str] = set()
        for identifier in ids:
            if identifier in seen:
                findings.append(
                    Finding("fail", "duplicate-id", identifier, f"Duplicate {label} id")
                )
            seen.add(identifier)
    return findings


def _check_rooms(control: ControlFile) -> list[Finding]:
    findings = []
    for room in control.rooms:
        for name, value in (("width", room.width_mm), ("length", room.length_mm)):
            if value < MIN_ROOM_MM:
                findings.append(
                    Finding(
                        "warn",
                        "suspicious-unit",
                        room.id,
                        f"{name} is {value:.0f} mm, which is under {MIN_ROOM_MM:.0f} mm. "
                        "Values are expected in millimetres.",
                    )
                )

        diagonals = [d for d in (room.diagonal_a_mm, room.diagonal_b_mm) if d is not None]
        if not diagonals:
            findings.append(
                Finding(
                    "warn",
                    "no-diagonal",
                    room.id,
                    "No diagonal measured. Without a diagonal you cannot tell whether the "
                    "corners are square, and in a pre-war building they are not.",
                )
            )
            continue

        expected = expected_diagonal_mm(room.width_mm, room.length_mm)
        for label, measured in (("a", room.diagonal_a_mm), ("b", room.diagonal_b_mm)):
            if measured is None:
                continue
            deviation = measured - expected
            if abs(deviation) > OUT_OF_SQUARE_NOTE_MM:
                findings.append(
                    Finding(
                        "warn",
                        "out-of-square",
                        f"{room.id}/diagonal_{label}",
                        f"Measured {measured:.0f} mm against {expected:.0f} mm for a true "
                        f"rectangle ({deviation:+.0f} mm). Model the deviation, do not "
                        "straighten it.",
                    )
                )

        if room.diagonal_a_mm is not None and room.diagonal_b_mm is not None:
            difference = abs(room.diagonal_a_mm - room.diagonal_b_mm)
            if difference > OUT_OF_SQUARE_NOTE_MM:
                findings.append(
                    Finding(
                        "warn",
                        "diagonals-differ",
                        room.id,
                        f"The two diagonals differ by {difference:.0f} mm, so the room is a "
                        "parallelogram rather than a rectangle.",
                    )
                )
    return findings


def _check_storey_heights(control: ControlFile) -> list[Finding]:
    findings = []
    by_storey: dict[str, list[StoreyHeight]] = {}
    for height in control.storey_heights:
        by_storey.setdefault(height.storey, []).append(height)
        if (
            height.floor_to_floor_mm is not None
            and height.floor_to_floor_mm <= height.floor_to_ceiling_mm
        ):
            findings.append(
                Finding(
                    "fail",
                    "impossible-height",
                    f"{height.storey}/{height.location}",
                    f"Floor-to-floor ({height.floor_to_floor_mm:.0f} mm) is not larger than "
                    f"floor-to-ceiling ({height.floor_to_ceiling_mm:.0f} mm). The floor "
                    "construction cannot have zero thickness.",
                )
            )

    for storey, heights in by_storey.items():
        if len(heights) < 3:
            findings.append(
                Finding(
                    "warn",
                    "thin-height-sample",
                    storey,
                    f"Only {len(heights)} height measurement(s). Take at least three per "
                    "storey; ceilings in old buildings are not flat.",
                )
            )
        values = [h.floor_to_ceiling_mm for h in heights]
        spread = max(values) - min(values)
        if spread > STOREY_HEIGHT_SPREAD_NOTE_MM:
            findings.append(
                Finding(
                    "warn",
                    "height-spread",
                    storey,
                    f"Floor-to-ceiling varies by {spread:.0f} mm across this storey. Pick one "
                    "level per storey in Revit and record the variation separately.",
                )
            )
    return findings


def _check_walls(control: ControlFile) -> list[Finding]:
    findings = []
    for wall in control.walls:
        if wall.thickness_mm < MIN_WALL_MM or wall.thickness_mm > MAX_WALL_MM:
            findings.append(
                Finding(
                    "fail",
                    "implausible-thickness",
                    wall.id,
                    f"{wall.thickness_mm:.0f} mm is outside {MIN_WALL_MM:.0f}-"
                    f"{MAX_WALL_MM:.0f} mm. Check the unit.",
                )
            )
    if not any(w.kind == "exterior" for w in control.walls):
        findings.append(
            Finding(
                "warn",
                "no-exterior-wall",
                "walls",
                "No exterior wall thickness recorded. Measure it in a window reveal, per "
                "facade, because building phases differ.",
            )
        )
    return findings


def _check_control_distances(control: ControlFile) -> list[Finding]:
    findings = []
    if len(control.control_distances) < 4:
        findings.append(
            Finding(
                "warn",
                "few-control-distances",
                "control_distances",
                f"Only {len(control.control_distances)} control distance(s). Aim for four to "
                "six per storey, including diagonals, or the cloud cannot be verified.",
            )
        )
    for distance in control.control_distances:
        if distance.from_marker == distance.to_marker:
            findings.append(
                Finding(
                    "fail",
                    "degenerate-distance",
                    distance.id,
                    "from_marker and to_marker are the same point.",
                )
            )
        if distance.length_mm <= 0:
            findings.append(
                Finding("fail", "non-positive-length", distance.id, "Length must be positive.")
            )
    return findings
