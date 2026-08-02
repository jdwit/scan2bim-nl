"""Shared HTTP plumbing.

Every public data service used here is open: no API keys, no accounts. Requests carry a
descriptive user agent because these are publicly funded services and anonymous scraping is
rude.
"""

from __future__ import annotations

from typing import Any

import httpx

USER_AGENT = "scan2bim-nl (+https://github.com/jdwit/scan2bim-nl)"
DEFAULT_TIMEOUT = httpx.Timeout(60.0, connect=15.0)


class SourceError(RuntimeError):
    """A data source returned something unusable."""


def client(transport: httpx.BaseTransport | None = None) -> httpx.Client:
    return httpx.Client(
        headers={"User-Agent": USER_AGENT},
        timeout=DEFAULT_TIMEOUT,
        follow_redirects=True,
        transport=transport,
    )


def get_json(url: str, params: dict[str, Any] | None = None, *, c: httpx.Client) -> Any:
    response = c.get(url, params=params)
    if response.status_code != 200:
        raise SourceError(f"{url} returned HTTP {response.status_code}")
    try:
        return response.json()
    except ValueError as exc:  # pragma: no cover - defensive
        raise SourceError(f"{url} did not return JSON") from exc


def get_bytes(
    url: str,
    params: dict[str, Any] | None = None,
    *,
    c: httpx.Client,
    expect_content_type: str | None = None,
) -> bytes:
    response = c.get(url, params=params)
    if response.status_code != 200:
        raise SourceError(f"{url} returned HTTP {response.status_code}")
    content_type = response.headers.get("content-type", "")
    if expect_content_type and expect_content_type not in content_type:
        raise SourceError(
            f"{url} returned content-type {content_type!r}, expected {expect_content_type!r}. "
            "The service usually reports errors as XML with a 200 status."
        )
    return response.content
