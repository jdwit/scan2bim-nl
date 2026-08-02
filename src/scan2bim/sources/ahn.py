"""AHN (Actueel Hoogtebestand Nederland) via the PDOK WCS.

Two coverages are published: `dtm_05m` (terrain, ground level) and `dsm_05m` (surface,
including roofs and trees), both at 0.5 m. Requesting a bbox subset beats downloading raw LAZ
tiles when all you need is the plot: you get exactly the area you asked for, as a GeoTIFF.

Open service, no key.
"""

from __future__ import annotations

import io
import math
from dataclasses import dataclass
from pathlib import Path

import httpx
import numpy as np
from PIL import Image

from scan2bim.http import SourceError, get_bytes

WCS_URL = "https://service.pdok.nl/rws/ahn/wcs/v1_0"
COVERAGES = ("dtm_05m", "dsm_05m")

# PDOK encodes nodata as the float32 maximum rather than NaN.
NODATA_THRESHOLD = 1e30

# GeoTIFF tags, see OGC GeoTIFF spec.
_TAG_PIXEL_SCALE = 33550
_TAG_TIEPOINT = 33922


@dataclass(frozen=True)
class Raster:
    """A height raster in RD coordinates, north-up."""

    values: np.ndarray  # shape (rows, cols), NaN where nodata
    origin_x: float  # RD easting of the top-left pixel corner
    origin_y: float  # RD northing of the top-left pixel corner
    pixel_size: float

    @property
    def shape(self) -> tuple[int, int]:
        return self.values.shape[0], self.values.shape[1]

    def stats(self) -> dict[str, float]:
        finite = self.values[np.isfinite(self.values)]
        if finite.size == 0:
            raise SourceError("Raster contains no valid height values")
        return {
            "count": float(finite.size),
            "min_m": float(finite.min()),
            "max_m": float(finite.max()),
            "mean_m": float(finite.mean()),
            "relief_m": float(finite.max() - finite.min()),
        }

    def to_xyz(self, step: int = 1) -> np.ndarray:
        """Point list (x, y, z) in RD metres, sampled every `step` pixels."""
        if step < 1:
            raise ValueError("step must be >= 1")
        rows, cols = self.shape
        row_idx = np.arange(0, rows, step)
        col_idx = np.arange(0, cols, step)
        grid = self.values[np.ix_(row_idx, col_idx)]
        # Pixel centres, hence the +0.5.
        xs = self.origin_x + (col_idx + 0.5) * self.pixel_size
        ys = self.origin_y - (row_idx + 0.5) * self.pixel_size
        xx, yy = np.meshgrid(xs, ys)
        stacked = np.column_stack([xx.ravel(), yy.ravel(), grid.ravel()])
        return stacked[np.isfinite(stacked[:, 2])]


def fetch(
    coverage: str,
    bbox: tuple[float, float, float, float],
    *,
    c: httpx.Client,
) -> bytes:
    if coverage not in COVERAGES:
        raise ValueError(f"Unknown coverage {coverage!r}, expected one of {COVERAGES}")
    xmin, ymin, xmax, ymax = bbox
    return get_bytes(
        WCS_URL,
        {
            "service": "WCS",
            "version": "2.0.1",
            "request": "GetCoverage",
            "coverageId": coverage,
            "subset": [f"x({xmin},{xmax})", f"y({ymin},{ymax})"],
            "format": "image/tiff",
        },
        c=c,
        expect_content_type="image/tiff",
    )


def read_raster(data: bytes, bbox: tuple[float, float, float, float]) -> Raster:
    """Decode a GeoTIFF. Georeferencing comes from the file, with the request bbox as fallback."""
    with Image.open(io.BytesIO(data)) as image:
        values = np.array(image, dtype=np.float64)
        tags = getattr(image, "tag_v2", {})

    values[~np.isfinite(values)] = np.nan
    values[np.abs(values) > NODATA_THRESHOLD] = np.nan

    pixel_scale = tags.get(_TAG_PIXEL_SCALE)
    tiepoint = tags.get(_TAG_TIEPOINT)
    if pixel_scale and tiepoint and len(tiepoint) >= 6:
        return Raster(
            values=values,
            origin_x=float(tiepoint[3]),
            origin_y=float(tiepoint[4]),
            pixel_size=float(pixel_scale[0]),
        )

    xmin, _ymin, xmax, ymax = bbox
    cols = values.shape[1]
    pixel_size = (xmax - xmin) / cols if cols else 0.5
    return Raster(values=values, origin_x=xmin, origin_y=ymax, pixel_size=pixel_size)


def write_points_csv(
    points: np.ndarray,
    path: Path,
    *,
    header: bool = False,
    offset: tuple[float, float, float] = (0.0, 0.0, 0.0),
) -> Path:
    """Comma separated x,y,z for Revit's toposolid CSV import.

    `offset` is subtracted from every point. Revit refuses to hold geometry far from its
    internal origin: hand it raw RD coordinates (hundreds of kilometres out) and it silently
    re-centres the points on the model, throwing the georeferencing away. Subtracting the
    project origin keeps the numbers small and the placement predictable.
    """
    ox, oy, oz = offset
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", encoding="utf-8") as handle:
        if header:
            handle.write("x,y,z\n")
        for x, y, z in points:
            handle.write(f"{x - ox:.3f},{y - oy:.3f},{z - oz:.3f}\n")
    return path


# Revit down samples any imported points file above this, silently, and the documentation
# warns that it costs accuracy. Staying under it keeps the terrain you asked for.
REVIT_POINT_LIMIT = 10_000


def suggested_step(
    bbox: tuple[float, float, float, float], target_points: int = REVIT_POINT_LIMIT
) -> int:
    """Keep point files under Revit's import limit."""
    xmin, ymin, xmax, ymax = bbox
    cells = ((xmax - xmin) / 0.5) * ((ymax - ymin) / 0.5)
    if cells <= target_points:
        return 1
    return max(1, math.ceil(math.sqrt(cells / target_points)))
