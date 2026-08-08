from __future__ import annotations

import json
from typing import Any

import httpx
import pytest


def json_transport(payload: Any, status_code: int = 200) -> httpx.MockTransport:
    def handler(_request: httpx.Request) -> httpx.Response:
        return httpx.Response(status_code, json=payload)

    return httpx.MockTransport(handler)


def bytes_transport(
    payload: bytes, content_type: str = "image/tiff", status_code: int = 200
) -> httpx.MockTransport:
    def handler(_request: httpx.Request) -> httpx.Response:
        return httpx.Response(status_code, content=payload, headers={"content-type": content_type})

    return httpx.MockTransport(handler)


@pytest.fixture
def locatieserver_payload() -> dict[str, Any]:
    return {
        "response": {
            "numFound": 1,
            "docs": [
                {
                    "type": "adres",
                    "weergavenaam": "Oranjelaan 5, 1217LV Hilversum",
                    "centroide_rd": "POINT(139657.02 471121.55)",
                    "centroide_ll": "POINT(5.16263667 52.22795454)",
                    "adresseerbaarobject_id": "0402010001608901",
                }
            ],
        }
    }


@pytest.fixture
def parcel_payload() -> dict[str, Any]:
    return {
        "type": "FeatureCollection",
        "features": [
            {
                "type": "Feature",
                "properties": {
                    "identificatieLokaalID": "13060051870000",
                    "kadastraleGemeenteWaarde": "Hilversum",
                    "sectie": "P",
                    "perceelnummer": 518,
                    "kadastraleGrootteWaarde": 1600.0,
                },
                "geometry": {
                    "type": "Polygon",
                    "coordinates": [
                        [
                            [139640.0, 471100.0],
                            [139680.0, 471100.0],
                            [139680.0, 471140.0],
                            [139640.0, 471140.0],
                            [139640.0, 471100.0],
                        ]
                    ],
                },
            }
        ],
    }


@pytest.fixture
def bag3d_payload() -> dict[str, Any]:
    return {
        "features": [
            {
                "CityObjects": {
                    "NL.IMBAG.Pand.0402100001482818": {
                        "type": "Building",
                        "attributes": {
                            "b3_bouwlagen": 2,
                            "b3_dak_type": "slanted",
                            "b3_h_maaiveld": 18.541,
                            "b3_h_nok": 27.13,
                            "b3_h_dak_max": 27.021,
                            "b3_h_dak_min": 21.49,
                            "oorspronkelijkbouwjaar": 1900,
                        },
                    },
                    "NL.IMBAG.Pand.0402100001482818-0": {
                        "type": "BuildingPart",
                        "attributes": {},
                    },
                }
            }
        ]
    }


@pytest.fixture
def control_yaml(tmp_path):
    path = tmp_path / "control.yaml"
    path.write_text(
        json.dumps(
            {
                "project": "test",
                "instrument": "Leica Disto D2",
                "storey_heights": [
                    {
                        "storey": "ground",
                        "location": "hall",
                        "floor_to_ceiling_mm": 3120,
                        "floor_to_floor_mm": 3450,
                    },
                    {"storey": "ground", "location": "living", "floor_to_ceiling_mm": 3125},
                    {"storey": "ground", "location": "kitchen", "floor_to_ceiling_mm": 3118},
                ],
                "rooms": [
                    {
                        "id": "living",
                        "storey": "ground",
                        "width_mm": 3000,
                        "length_mm": 4000,
                        "diagonal_a_mm": 5000,
                        "diagonal_b_mm": 5005,
                    }
                ],
                "walls": [
                    {"id": "facade-south", "kind": "exterior", "thickness_mm": 320},
                    {"id": "partition", "kind": "interior", "thickness_mm": 100},
                ],
                "control_distances": [
                    {"id": "cd-1", "from_marker": "A", "to_marker": "B", "length_mm": 12000},
                    {"id": "cd-2", "from_marker": "A", "to_marker": "C", "length_mm": 8000},
                    # B-C closes the triangle: sqrt(12000^2 + 8000^2) rounded to the millimetre.
                    {"id": "cd-3", "from_marker": "B", "to_marker": "C", "length_mm": 14422},
                    {"id": "cd-4", "from_marker": "A", "to_marker": "D", "length_mm": 15000},
                ],
            }
        ),
        encoding="utf-8",
    )
    return path
