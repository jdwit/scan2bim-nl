"""PDOK Locatieserver: address -> RD coordinates and BAG identifiers.

Open service, no key. https://api.pdok.nl/bzk/locatieserver/search/v3_1/
"""

from __future__ import annotations

import re
from dataclasses import dataclass

import httpx

from scan2bim.http import SourceError, get_json

BASE_URL = "https://api.pdok.nl/bzk/locatieserver/search/v3_1/free"

_POINT = re.compile(r"POINT\(\s*([0-9.eE+-]+)\s+([0-9.eE+-]+)\s*\)")


@dataclass(frozen=True)
class AddressHit:
    display_name: str
    rd_x: float
    rd_y: float
    lon: float
    lat: float
    object_id: str | None = None

    @property
    def postcode(self) -> str | None:
        match = re.search(r"\b(\d{4}\s?[A-Z]{2})\b", self.display_name)
        return match.group(1).replace(" ", "") if match else None

    @property
    def city(self) -> str | None:
        # "Oranjelaan 5, 1217LV Hilversum" -> "Hilversum"
        tail = self.display_name.split(",")[-1].strip()
        parts = tail.split(None, 1)
        return parts[1] if len(parts) == 2 else None


def _parse_point(value: str | None) -> tuple[float, float]:
    if not value:
        raise SourceError("Locatieserver returned a result without coordinates")
    match = _POINT.match(value.strip())
    if not match:
        raise SourceError(f"Could not parse WKT point {value!r}")
    return float(match.group(1)), float(match.group(2))


def search(query: str, *, c: httpx.Client, rows: int = 5) -> list[AddressHit]:
    """Search addresses.

    Restricted to `type:adres`, so a result is a building rather than a street.
    """
    payload = get_json(
        BASE_URL,
        {
            "q": query,
            "fq": "type:adres",
            "rows": rows,
            "fl": "weergavenaam,centroide_rd,centroide_ll,adresseerbaarobject_id",
        },
        c=c,
    )
    docs = payload.get("response", {}).get("docs", [])
    hits: list[AddressHit] = []
    for doc in docs:
        rd_x, rd_y = _parse_point(doc.get("centroide_rd"))
        lon, lat = _parse_point(doc.get("centroide_ll"))
        hits.append(
            AddressHit(
                display_name=doc.get("weergavenaam", ""),
                rd_x=rd_x,
                rd_y=rd_y,
                lon=lon,
                lat=lat,
                object_id=doc.get("adresseerbaarobject_id"),
            )
        )
    return hits


def resolve_one(query: str, *, c: httpx.Client) -> AddressHit:
    hits = search(query, c=c, rows=1)
    if not hits:
        raise SourceError(f"No address found for {query!r}")
    return hits[0]
