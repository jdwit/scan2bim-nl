"""Project state: a directory with a project.toml and a fixed folder layout."""

from __future__ import annotations

import tomllib
from pathlib import Path

import tomli_w
from pydantic import BaseModel, Field

PROJECT_FILE = "project.toml"

# Folders created by `scan2bim project init`. raw/ is immutable input, derived/ is generated
# and safe to delete, control/ is hand-edited field data.
LAYOUT = ("control", "raw", "raw/scans", "raw/photos", "derived", "reports")


class Project(BaseModel):
    """Everything the tool needs to know about one building."""

    name: str
    address: str | None = None
    postcode: str | None = None
    city: str | None = None
    rd_x: float | None = Field(default=None, description="RD (EPSG:28992) easting in metres")
    rd_y: float | None = Field(default=None, description="RD (EPSG:28992) northing in metres")
    bag_object_id: str | None = None
    radius_m: float = Field(default=60.0, description="Half-width of the area of interest")

    @property
    def has_location(self) -> bool:
        return self.rd_x is not None and self.rd_y is not None

    def bbox(self, radius_m: float | None = None) -> tuple[float, float, float, float]:
        """Square bounding box in RD around the project origin: (xmin, ymin, xmax, ymax)."""
        if not self.has_location:
            raise ValueError(
                "Project has no coordinates yet. Run `scan2bim address resolve` first."
            )
        r = radius_m if radius_m is not None else self.radius_m
        assert self.rd_x is not None and self.rd_y is not None
        return (self.rd_x - r, self.rd_y - r, self.rd_x + r, self.rd_y + r)


def find_project_dir(start: Path | None = None) -> Path:
    """Walk up from `start` until a project.toml is found."""
    current = (start or Path.cwd()).resolve()
    for candidate in [current, *current.parents]:
        if (candidate / PROJECT_FILE).is_file():
            return candidate
    raise FileNotFoundError(
        f"No {PROJECT_FILE} found here or in any parent directory. "
        "Run `scan2bim project init <name>` first."
    )


def load(directory: Path | None = None) -> tuple[Path, Project]:
    root = find_project_dir(directory)
    data = tomllib.loads((root / PROJECT_FILE).read_text(encoding="utf-8"))
    return root, Project.model_validate(data.get("project", {}))


def save(root: Path, project: Project) -> Path:
    path = root / PROJECT_FILE
    payload = {"project": project.model_dump(exclude_none=True)}
    path.write_text(tomli_w.dumps(payload), encoding="utf-8")
    return path


def create_layout(root: Path) -> list[Path]:
    created = []
    for folder in LAYOUT:
        target = root / folder
        if not target.exists():
            target.mkdir(parents=True)
            created.append(target)
    return created
