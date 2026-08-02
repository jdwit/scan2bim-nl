"""3DBAG (TU Delft): LoD2.2 building models for every building in the Netherlands.

Note on the response: this is an OGC API Features collection whose features embed CityJSON
objects with quantised integer vertices, not a standalone CityJSON document. The saved file is
therefore useful for its attributes and for feeding a CityJSON-aware pipeline that applies the
transform, and is not something you can hand to a viewer expecting plain CityJSON.

Useful as an independent check on the geometry you measure yourself: ridge height, eaves
height, ground level and number of storeys, derived from national aerial LiDAR rather than
from your own scan. Also gives you the neighbours, which matters for daylight and shadow
questions around an extension.

Open service, no key. https://api.3dbag.nl
"""

from __future__ import annotations

import json
from dataclasses import dataclass
from pathlib import Path
from typing import Any

import httpx

from scan2bim.http import get_json

API_URL = "https://api.3dbag.nl/collections/pand/items"


@dataclass(frozen=True)
class Building:
    """The handful of 3DBAG attributes worth quoting in a design discussion."""

    identificatie: str
    ground_level_m: float | None  # b3_h_maaiveld, metres NAP
    ridge_height_m: float | None  # b3_h_nok
    roof_max_m: float | None  # b3_h_dak_max
    roof_min_m: float | None  # b3_h_dak_min (eaves in practice)
    storeys: int | None
    roof_type: str | None
    construction_year: int | None

    @property
    def height_above_ground_m(self) -> float | None:
        if self.ridge_height_m is None or self.ground_level_m is None:
            return None
        return round(self.ridge_height_m - self.ground_level_m, 2)

    @property
    def eaves_above_ground_m(self) -> float | None:
        if self.roof_min_m is None or self.ground_level_m is None:
            return None
        return round(self.roof_min_m - self.ground_level_m, 2)


def fetch(
    bbox: tuple[float, float, float, float],
    *,
    c: httpx.Client,
    limit: int = 25,
) -> dict[str, Any]:
    xmin, ymin, xmax, ymax = bbox
    return get_json(
        API_URL,
        {"bbox": f"{xmin},{ymin},{xmax},{ymax}", "limit": limit},
        c=c,
    )


def parse(payload: dict[str, Any]) -> list[Building]:
    """Flatten the CityJSON features into something you can put in a table."""
    buildings: list[Building] = []
    for feature in payload.get("features", []):
        for identificatie, city_object in (feature.get("CityObjects") or {}).items():
            attributes = city_object.get("attributes") or {}
            if "b3_h_maaiveld" not in attributes and "b3_h_nok" not in attributes:
                continue  # building parts inherit from their parent, skip them
            buildings.append(
                Building(
                    identificatie=identificatie,
                    ground_level_m=_as_float(attributes.get("b3_h_maaiveld")),
                    ridge_height_m=_as_float(attributes.get("b3_h_nok")),
                    roof_max_m=_as_float(attributes.get("b3_h_dak_max")),
                    roof_min_m=_as_float(attributes.get("b3_h_dak_min")),
                    storeys=_as_int(attributes.get("b3_bouwlagen")),
                    roof_type=attributes.get("b3_dak_type"),
                    construction_year=_as_int(attributes.get("oorspronkelijkbouwjaar")),
                )
            )
    return buildings


def truncated(payload: dict[str, Any], limit: int) -> bool:
    """True when the service has more buildings than were returned."""
    matched = payload.get("numberMatched")
    return isinstance(matched, int) and matched > limit


def write_features(payload: dict[str, Any], path: Path) -> Path:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, indent=2), encoding="utf-8")
    return path


def _as_float(value: Any) -> float | None:
    try:
        return round(float(value), 3)
    except (TypeError, ValueError):
        return None


def _as_int(value: Any) -> int | None:
    try:
        return int(value)
    except (TypeError, ValueError):
        return None
