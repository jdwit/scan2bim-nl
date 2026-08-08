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


def to_dxf(
    collection: dict[str, Any],
    path: Path,
    *,
    layer: str = "PERCEEL",
    elevation: float = 0.0,
    offset: tuple[float, float] = (0.0, 0.0),
) -> Path:
    """Minimal DXF R12 with one POLYLINE per ring, in metres.

    Hand-rolled on purpose: a CAD library is a heavy dependency for a flat list of coordinates.
    But minimal is not the same as sloppy, so this writes the parts a reader needs:

    - a HEADER declaring `$INSUNITS` = metres and `$MEASUREMENT` = metric, so an importer does
      not have to guess the scale
    - a TABLES section defining the layer the entities claim to be on
    - the dummy 10/20/30 point the R12 spec requires on POLYLINE
    - an explicit `30` elevation on every vertex, since a model referenced to NAP puts a
      Z=0 parcel line metres below the building

    `offset` is subtracted from every coordinate, matching the terrain export.
    """
    ox, oy = offset
    tags: list[tuple[int, object]] = [
        (0, "SECTION"),
        (2, "HEADER"),
        (9, "$ACADVER"),
        (1, "AC1009"),
        (9, "$INSUNITS"),
        (70, 6),  # 6 = metres
        (9, "$MEASUREMENT"),
        (70, 1),  # 1 = metric
        (0, "ENDSEC"),
        (0, "SECTION"),
        (2, "TABLES"),
        (0, "TABLE"),
        (2, "LAYER"),
        (70, 1),
        (0, "LAYER"),
        (2, layer),
        (70, 0),
        (62, 7),
        (6, "CONTINUOUS"),
        (0, "ENDTAB"),
        (0, "ENDSEC"),
        (0, "SECTION"),
        (2, "ENTITIES"),
    ]
    for feature in collection.get("features", []):
        for ring in _rings(feature.get("geometry") or {}):
            tags += [
                (0, "POLYLINE"),
                (8, layer),
                (66, 1),
                (70, 1),
                # R12 requires a dummy point on the POLYLINE header itself.
                (10, 0.0),
                (20, 0.0),
                (30, elevation),
            ]
            for x, y in ring:
                tags += [
                    (0, "VERTEX"),
                    (8, layer),
                    (10, x - ox),
                    (20, y - oy),
                    (30, elevation),
                ]
            tags += [(0, "SEQEND"), (8, layer)]
    tags += [(0, "ENDSEC"), (0, "EOF")]

    lines = []
    for code, value in tags:
        lines.append(str(code))
        lines.append(f"{value:.3f}" if isinstance(value, float) else str(value))
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
