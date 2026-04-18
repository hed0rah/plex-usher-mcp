"""Plex HTTP client.

Plex defaults to XML; we force JSON via the Accept header. The token is always
sent as a query param (`X-Plex-Token`). Local LAN certs are self-signed so we
skip TLS verification. The token is never returned in tool responses.
"""

from __future__ import annotations

from typing import Any

import httpx

from .config import Config

# Endpoints that return 400 when the parent has no children instead of
# returning an empty MediaContainer. Treat 400 on these as "empty".
_EMPTY_OK_SUFFIX = "/children"


class PlexError(RuntimeError):
    pass


class PlexClient:
    def __init__(self, config: Config) -> None:
        self._base = config.plex_address
        self._token = config.plex_token
        self._http = httpx.AsyncClient(
            base_url=self._base,
            headers={"Accept": "application/json"},
            params={"X-Plex-Token": self._token},
            verify=False,
            timeout=15.0,
        )

    async def aclose(self) -> None:
        await self._http.aclose()

    async def get_json(self, path: str, params: dict[str, Any] | None = None) -> dict[str, Any]:
        try:
            response = await self._http.get(path, params=params)
        except httpx.HTTPError as exc:
            raise PlexError(f"plex request failed: {exc}") from exc

        if response.status_code == 400 and path.endswith(_EMPTY_OK_SUFFIX):
            return {"MediaContainer": {"Metadata": []}}

        if response.status_code >= 400:
            raise PlexError(
                f"plex returned {response.status_code} for {path}: {response.text[:200]}"
            )

        try:
            return response.json()
        except ValueError as exc:
            raise PlexError(f"plex returned non-JSON for {path}") from exc

    async def stream_image(self, image_path: str) -> bytes:
        """Fetch a binary image (thumb/art). `image_path` is the path from the metadata."""
        try:
            response = await self._http.get(image_path)
        except httpx.HTTPError as exc:
            raise PlexError(f"plex image fetch failed: {exc}") from exc
        if response.status_code >= 400:
            raise PlexError(f"plex image fetch returned {response.status_code} for {image_path}")
        return response.content
