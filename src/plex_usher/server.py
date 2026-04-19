"""FastMCP server for Plex Media Server.

All tools carry MCP annotations (readOnly/idempotent/destructive/openWorld hints).
Read tools are strictly read-only. plex_save_poster is the only tool that writes
to the server's filesystem.
"""

from __future__ import annotations

import asyncio
from contextlib import asynccontextmanager
from collections.abc import AsyncIterator
from pathlib import Path
from typing import Any

from fastmcp import FastMCP
from fastmcp.utilities.types import Image
from mcp.types import ToolAnnotations
from rapidfuzz import fuzz

from .client import PlexClient
from .config import Config
from .models import (
    ItemDetail,
    ItemSummary,
    Library,
    LibraryStats,
    PosterSaveResult,
    SearchCandidate,
)
from .utils import (
    parse_item_detail,
    parse_item_summary,
    parse_library,
    parse_library_stats,
)

_client: PlexClient | None = None
_client_lock = asyncio.Lock()


async def _get_client() -> PlexClient:
    global _client
    async with _client_lock:
        if _client is None:
            _client = PlexClient(Config.from_env())
    return _client


@asynccontextmanager
async def _lifespan(_server: FastMCP) -> AsyncIterator[None]:
    try:
        yield
    finally:
        global _client
        if _client is not None:
            await _client.aclose()
            _client = None


mcp: FastMCP = FastMCP("plex-usher", lifespan=_lifespan)


def _container(raw: dict[str, Any]) -> list[dict[str, Any]]:
    return raw.get("MediaContainer", {}).get("Metadata", []) or []


def _directories(raw: dict[str, Any]) -> list[dict[str, Any]]:
    return raw.get("MediaContainer", {}).get("Directory", []) or []


def _total_size(raw: dict[str, Any]) -> int:
    return int(raw.get("MediaContainer", {}).get("totalSize", 0))


@mcp.tool(
    name="plex_list_libraries",
    tags={"libraries", "discovery"},
    annotations=ToolAnnotations(
        title="List Plex Libraries",
        readOnlyHint=True,
        idempotentHint=True,
        openWorldHint=False,
    ),
)
async def plex_list_libraries() -> list[Library]:
    """List all library sections on the Plex server.

    Returns each section's key (use as section_key in other tools), title, and type
    (movie | show | artist | photo). No item counts — call plex_library_stats for that.
    """
    client = await _get_client()
    raw = await client.get_json("/library/sections/all")
    return [parse_library(d) for d in _directories(raw)]


@mcp.tool(
    name="plex_library_stats",
    tags={"libraries", "metadata"},
    annotations=ToolAnnotations(
        title="Plex Library Stats",
        readOnlyHint=True,
        idempotentHint=True,
        openWorldHint=False,
    ),
)
async def plex_library_stats(section_key: str) -> LibraryStats:
    """Return total and unwatched item counts for a library section.

    Cheap: uses Container-Size=0 so Plex returns the totalSize without payload.
    unwatched_count is None for libraries where watched state doesn't apply (music, photos).
    """
    client = await _get_client()
    libs_raw = await client.get_json("/library/sections/all")
    library = next(
        (parse_library(d) for d in _directories(libs_raw) if str(d["key"]) == section_key),
        None,
    )
    if library is None:
        raise ValueError(f"no library with key={section_key}")

    total_raw = await client.get_json(
        f"/library/sections/{section_key}/all",
        params={"X-Plex-Container-Start": 0, "X-Plex-Container-Size": 0},
    )
    total = _total_size(total_raw) or len(_container(total_raw))

    unwatched: int | None = None
    if library.type in {"movie", "show"}:
        unwatched_raw = await client.get_json(
            f"/library/sections/{section_key}/all",
            params={
                "unwatched": 1,
                "X-Plex-Container-Start": 0,
                "X-Plex-Container-Size": 0,
            },
        )
        unwatched = _total_size(unwatched_raw) or len(_container(unwatched_raw))

    return parse_library_stats(library, total, unwatched)


@mcp.tool(
    name="plex_list_items",
    tags={"items", "browse"},
    annotations=ToolAnnotations(
        title="List Items in Plex Library",
        readOnlyHint=True,
        idempotentHint=True,
        openWorldHint=False,
    ),
)
async def plex_list_items(
    section_key: str,
    limit: int = 50,
    offset: int = 0,
    sort: str = "titleSort:asc",
    unwatched: bool = False,
    genre: str | None = None,
    year_min: int | None = None,
    year_max: int | None = None,
    rating_min: float | None = None,
) -> list[ItemSummary]:
    """List items in a library section with optional filters.

    Filters are applied server-side by Plex:
    - unwatched=True: only items with view_count == 0
    - genre: exact match on genre tag (e.g. "Horror", "Anime"). Case-sensitive on Plex.
    - year_min / year_max: inclusive bounds on release year
    - rating_min: minimum user rating (1-10 scale)

    sort examples: titleSort:asc, addedAt:desc, year:desc, rating:desc, lastViewedAt:desc
    """
    params: dict[str, Any] = {
        "X-Plex-Container-Start": offset,
        "X-Plex-Container-Size": limit,
        "sort": sort,
    }
    if unwatched:
        params["unwatched"] = 1
    if genre:
        params["genre"] = genre
    # Plex's >> and << operators are strictly greater/less than (exclusive).
    # Subtract/add to make the documented year_min/year_max/rating_min bounds
    # behave inclusively. Do NOT "simplify" these without changing the operator.
    if year_min is not None:
        params["year>>"] = year_min - 1
    if year_max is not None:
        params["year<<"] = year_max + 1
    if rating_min is not None:
        params["rating>>"] = rating_min - 0.0001

    client = await _get_client()
    raw = await client.get_json(f"/library/sections/{section_key}/all", params=params)
    return [parse_item_summary(m) for m in _container(raw)]


@mcp.tool(
    name="plex_get_item",
    tags={"items", "metadata"},
    annotations=ToolAnnotations(
        title="Get Plex Item Detail",
        readOnlyHint=True,
        idempotentHint=True,
        openWorldHint=False,
    ),
)
async def plex_get_item(rating_key: str) -> ItemDetail:
    """Fetch full metadata for one item.

    Returns structured fields (genres, directors, writers, actors as arrays) AND
    pre-formatted strings (genres_formatted, actors_formatted, duration_formatted)
    ready to paste into a note. Also includes watched state, view count, added date,
    last-viewed date, and file paths on disk.
    """
    client = await _get_client()
    raw = await client.get_json(f"/library/metadata/{rating_key}")
    items = _container(raw)
    if not items:
        raise ValueError(f"no item with rating_key={rating_key}")
    return parse_item_detail(items[0])


@mcp.tool(
    name="plex_list_seasons",
    tags={"shows", "browse"},
    annotations=ToolAnnotations(
        title="List Seasons of a Show",
        readOnlyHint=True,
        idempotentHint=True,
        openWorldHint=False,
    ),
)
async def plex_list_seasons(show_rating_key: str) -> list[ItemSummary]:
    """List seasons for a show."""
    client = await _get_client()
    raw = await client.get_json(f"/library/metadata/{show_rating_key}/children")
    return [parse_item_summary(m) for m in _container(raw)]


@mcp.tool(
    name="plex_list_episodes",
    tags={"shows", "browse"},
    annotations=ToolAnnotations(
        title="List Episodes in a Season",
        readOnlyHint=True,
        idempotentHint=True,
        openWorldHint=False,
    ),
)
async def plex_list_episodes(season_rating_key: str) -> list[ItemSummary]:
    """List episodes in a season."""
    client = await _get_client()
    raw = await client.get_json(f"/library/metadata/{season_rating_key}/children")
    return [parse_item_summary(m) for m in _container(raw)]


@mcp.tool(
    name="plex_recently_added",
    tags={"items", "discovery"},
    annotations=ToolAnnotations(
        title="Recently Added to Plex",
        readOnlyHint=True,
        idempotentHint=False,  # new items appear over time
        openWorldHint=False,
    ),
)
async def plex_recently_added(limit: int = 25) -> list[ItemSummary]:
    """Items recently added across all libraries. Non-idempotent: output drifts as new
    items are added to Plex."""
    client = await _get_client()
    raw = await client.get_json(
        "/library/recentlyAdded",
        params={"X-Plex-Container-Start": 0, "X-Plex-Container-Size": limit},
    )
    return [parse_item_summary(m) for m in _container(raw)]


@mcp.tool(
    name="plex_on_deck",
    tags={"items", "discovery"},
    annotations=ToolAnnotations(
        title="Plex On-Deck (Continue Watching)",
        readOnlyHint=True,
        idempotentHint=False,  # changes as user watches
        openWorldHint=False,
    ),
)
async def plex_on_deck() -> list[ItemSummary]:
    """Continue-watching items (Plex's 'On Deck' list). Non-idempotent: output
    changes as the user watches things."""
    client = await _get_client()
    raw = await client.get_json("/library/onDeck")
    return [parse_item_summary(m) for m in _container(raw)]


@mcp.tool(
    name="plex_search",
    tags={"search", "discovery"},
    annotations=ToolAnnotations(
        title="Fuzzy Search Plex",
        readOnlyHint=True,
        idempotentHint=True,
        openWorldHint=False,
    ),
)
async def plex_search(
    query: str,
    limit: int = 10,
    section_key: str | None = None,
) -> list[SearchCandidate]:
    """Fuzzy-search Plex and return top-N candidates ranked by match score.

    For ambiguous queries ('Aliens 2', partial titles, misspellings). The calling
    model should inspect the candidates, pick the intended one by rating_key, then
    call plex_get_item or plex_get_poster. Each candidate includes the library
    section name so multi-library hits can be disambiguated.

    Scores are 0-100 (rapidfuzz WRatio); treat <60 as unreliable.
    """
    client = await _get_client()
    params: dict[str, Any] = {"query": query}
    if section_key:
        params["sectionId"] = section_key

    raw = await client.get_json("/search", params=params)
    results: list[SearchCandidate] = []
    for m in _container(raw):
        title = m.get("title", "")
        year = m.get("year")
        haystack = f"{title} {year}" if year else title
        score = fuzz.WRatio(query, haystack)
        results.append(
            SearchCandidate(
                rating_key=str(m["ratingKey"]),
                title=title,
                type=m.get("type", "unknown"),
                year=year,
                library=m.get("librarySectionTitle"),
                score=float(score),
            )
        )
    results.sort(key=lambda c: c.score, reverse=True)
    return results[:limit]


@mcp.tool(
    name="plex_get_poster",
    tags={"media", "image"},
    annotations=ToolAnnotations(
        title="Get Plex Poster (read-only)",
        readOnlyHint=True,
        idempotentHint=True,
        openWorldHint=False,
    ),
)
async def plex_get_poster(rating_key: str) -> Image:
    """Fetch the poster (thumb) for an item as MCP Image content.

    Pure read: nothing is written to disk. The caller receives the image bytes
    and decides what to do with them (display inline, pass to another tool, etc.).
    For clients that can't persist binary MCP content, use plex_save_poster instead.
    Raises if the item has no poster.
    """
    client = await _get_client()
    raw = await client.get_json(f"/library/metadata/{rating_key}")
    items = _container(raw)
    if not items:
        raise ValueError(f"no item with rating_key={rating_key}")
    thumb = items[0].get("thumb")
    if not thumb:
        title = items[0].get("title", rating_key)
        raise ValueError(f"item {title!r} has no poster thumb")
    data = await client.stream_image(thumb)
    return Image(data=data, format="jpeg")


@mcp.tool(
    name="plex_save_poster",
    tags={"media", "image", "write"},
    annotations=ToolAnnotations(
        title="Save Plex Poster to Disk",
        readOnlyHint=False,
        destructiveHint=True,  # overwrites save_to if the file exists
        idempotentHint=True,  # same args = same bytes at same path
        openWorldHint=False,
    ),
)
async def plex_save_poster(rating_key: str, save_to: str) -> PosterSaveResult:
    """Fetch a poster from Plex and write it to the MCP server's filesystem.

    save_to: absolute path where the JPEG should be written on the server host.
    Parent directories are created. If the file already exists it is overwritten
    (hence destructiveHint=True). Returns path, byte count, and item metadata —
    no inline image content, to keep this path cheap for callers that just need
    to confirm the write.

    Only useful when the caller and MCP server share a filesystem (e.g. local
    stdio transport). For clients that can persist binary MCP content directly,
    prefer plex_get_poster and handle the write client-side.
    """
    client = await _get_client()
    raw = await client.get_json(f"/library/metadata/{rating_key}")
    items = _container(raw)
    if not items:
        raise ValueError(f"no item with rating_key={rating_key}")

    meta = items[0]
    thumb = meta.get("thumb")
    if not thumb:
        raise ValueError(f"item {meta.get('title', rating_key)!r} has no poster thumb")

    data = await client.stream_image(thumb)
    target = Path(save_to).expanduser()
    target.parent.mkdir(parents=True, exist_ok=True)
    target.write_bytes(data)

    return PosterSaveResult(
        rating_key=str(meta["ratingKey"]),
        title=meta.get("title", ""),
        year=meta.get("year"),
        path=str(target),
        bytes_written=len(data),
    )


def main() -> None:
    mcp.run()


if __name__ == "__main__":
    main()
