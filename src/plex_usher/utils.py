"""Small helpers: slug generation, Plex response flattening, pretty-formatting."""

from __future__ import annotations

import re
from typing import Any

from .models import ItemDetail, ItemSummary, Library, LibraryStats, Person

_SLUG_STRIP = re.compile(r"[^a-z0-9-]+")
_SLUG_DASHES = re.compile(r"-+")


def slugify(text: str) -> str:
    text = text.lower().replace(" ", "-")
    text = _SLUG_STRIP.sub("", text)
    text = _SLUG_DASHES.sub("-", text).strip("-")
    return text or "untitled"


def _tags(raw: list[dict[str, Any]] | None) -> list[str]:
    if not raw:
        return []
    return [t["tag"] for t in raw if t.get("tag")]


def _people(raw: list[dict[str, Any]] | None) -> list[Person]:
    if not raw:
        return []
    return [Person(name=p["tag"], role=p.get("role")) for p in raw if p.get("tag")]


def _file_paths(raw: list[dict[str, Any]] | None) -> list[str]:
    paths: list[str] = []
    for media in raw or []:
        for part in media.get("Part", []) or []:
            if part.get("file"):
                paths.append(part["file"])
    return paths


def _format_actors(actors: list[Person], limit: int = 8) -> str:
    if not actors:
        return ""
    parts = []
    for a in actors[:limit]:
        parts.append(f"{a.name} ({a.role})" if a.role else a.name)
    return ", ".join(parts)


def _format_duration_ms(duration_ms: int | None) -> str:
    if not duration_ms:
        return ""
    minutes = round(duration_ms / 60000)
    return f"{minutes} min"


def parse_library(raw: dict[str, Any]) -> Library:
    return Library(key=str(raw["key"]), title=raw["title"], type=raw.get("type", "unknown"))


def parse_library_stats(
    library: Library, total: int, unwatched: int | None
) -> LibraryStats:
    return LibraryStats(
        key=library.key,
        title=library.title,
        type=library.type,
        total_count=total,
        unwatched_count=unwatched,
    )


def parse_item_summary(raw: dict[str, Any]) -> ItemSummary:
    view_count = int(raw.get("viewCount", 0))
    return ItemSummary(
        rating_key=str(raw["ratingKey"]),
        title=raw.get("title", ""),
        type=raw.get("type", "unknown"),
        year=raw.get("year"),
        rating=raw.get("rating"),
        view_count=view_count,
        watched=view_count > 0,
        last_viewed_at=raw.get("lastViewedAt"),
        added_at=raw.get("addedAt"),
        library=raw.get("librarySectionTitle"),
        thumb=raw.get("thumb"),
    )


def parse_item_detail(raw: dict[str, Any]) -> ItemDetail:
    view_count = int(raw.get("viewCount", 0))
    genres = _tags(raw.get("Genre"))
    directors = _tags(raw.get("Director"))
    writers = _tags(raw.get("Writer"))
    actors = _people(raw.get("Role"))
    duration_ms = raw.get("duration")

    return ItemDetail(
        rating_key=str(raw["ratingKey"]),
        title=raw.get("title", ""),
        type=raw.get("type", "unknown"),
        year=raw.get("year"),
        summary=raw.get("summary"),
        tagline=raw.get("tagline"),
        content_rating=raw.get("contentRating"),
        duration_ms=duration_ms,
        user_rating=raw.get("rating"),
        audience_rating=raw.get("audienceRating"),
        genres=genres,
        directors=directors,
        writers=writers,
        actors=actors,
        studio=raw.get("studio"),
        originally_available_at=raw.get("originallyAvailableAt"),
        added_at=raw.get("addedAt"),
        last_viewed_at=raw.get("lastViewedAt"),
        view_count=view_count,
        watched=view_count > 0,
        file_paths=_file_paths(raw.get("Media")),
        thumb=raw.get("thumb"),
        genres_formatted=", ".join(genres),
        directors_formatted=", ".join(directors),
        writers_formatted=", ".join(writers),
        actors_formatted=_format_actors(actors),
        duration_formatted=_format_duration_ms(duration_ms),
    )
