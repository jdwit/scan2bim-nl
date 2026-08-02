"""PDOK Kadastrale Kaart (WFS): parcel boundaries.

The parcel boundary belongs in the model as surveyed data, not as something traced from a
scan. Open service, no key.
"""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any

import httpx

from scan2bim.http import get_json

WFS_URL = "https://service.pdok.nl/kadaster/kadastralekaart/wfs/v5_0"
CRS = "EPSG:28992"


def fetch_layer(
    layer: str,
    bbox: tuple[float, float, float, float],
    *,
    c: httpx.Client,
    count: int = 200,
) -> dict[str, Any]:
    """GeoJSON FeatureCollection for one WFS layer inside `bbox` (RD)."""
    xmin, ymin, xmax, ymax = bbox
    return get_json(
        WFS_URL,
        {
            "service": "WFS",
            "version": "2.0.0",
            "request": "GetFeature",
            "typeNames": layer,
            "outputFormat": "application/json",
            "srsName": CRS,
            "count": count,
            "bbox": f"{xmin},{ymin},{xmax},{ymax},{CRS}",
        },
        c=c,
    )


def parcels(bbox: tuple[float, float, float, float], *, c: httpx.Client) -> dict[str, Any]:
    return fetch_layer("kadastralekaart:Perceel", bbox, c=c)


def buildings(bbox: tuple[float, float, float, float], *, c: httpx.Client) -> dict[str, Any]:
    return fetch_layer("kadastralekaart:Bebouwing", bbox, c=c)


def summarise(collection: dict[str, Any]) -> list[dict[str, Any]]:
    """Pull the fields you actually quote in a permit application."""
    rows = []
    for feature in collection.get("features", []):
        props = feature.get("properties", {})
        rows.append(
            {
                "id": props.get("identificatieLokaalID"),
                "gemeente": props.get("kadastraleGemeenteWaarde"),
                "sectie": props.get("sectie"),
                "perceelnummer": props.get("perceelnummer"),
                "oppervlakte_m2": props.get("kadastraleGrootteWaarde"),
            }
        )
    return rows


def write_geojson(collection: dict[str, Any], path: Path) -> Path:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(collection, indent=2), encoding="utf-8")
    return path


def to_dxf(collection: dict[str, Any], path: Path) -> Path:
    """Minimal DXF R12 with one LWPOLYLINE per ring, in RD metres.

    Deliberately hand-rolled: a full CAD library is a heavy dependency for what is a flat list
    of coordinates, and R12 polylines import everywhere.
    """
    lines: list[str] = ["0", "SECTION", "2", "ENTITIES"]
    for feature in collection.get("features", []):
        geometry = feature.get("geometry") or {}
        for ring in _rings(geometry):
            lines += ["0", "POLYLINE", "8", "PERCEEL", "66", "1", "70", "1"]
            for x, y in ring:
                lines += ["0", "VERTEX", "8", "PERCEEL", "10", f"{x:.3f}", "20", f"{y:.3f}"]
            lines += ["0", "SEQEND"]
    lines += ["0", "ENDSEC", "0", "EOF"]
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text("\n".join(lines) + "\n", encoding="utf-8")
    return path


def _rings(geometry: dict[str, Any]) -> list[list[tuple[float, float]]]:
    kind = geometry.get("type")
    coords = geometry.get("coordinates") or []
    if kind == "Polygon":
        return [[(float(x), float(y)) for x, y, *_ in ring] for ring in coords]
    if kind == "MultiPolygon":
        return [
            [(float(x), float(y)) for x, y, *_ in ring] for polygon in coords for ring in polygon
        ]
    if kind == "LineString":
        return [[(float(x), float(y)) for x, y, *_ in coords]]
    if kind == "MultiLineString":
        return [[(float(x), float(y)) for x, y, *_ in line] for line in coords]
    return []
