"""Typed shapes returned from the MCP tools.

Structured data + pre-formatted text fields where the caller will usually
just want to drop a human-readable string into a note.
"""

from __future__ import annotations

from pydantic import BaseModel, Field


class Library(BaseModel):
    key: str
    title: str
    type: str  # movie | show | artist | photo


class LibraryStats(BaseModel):
    key: str
    title: str
    type: str
    total_count: int
    unwatched_count: int | None = None  # None for types where watched state is meaningless


class ItemSummary(BaseModel):
    rating_key: str
    title: str
    type: str
    year: int | None = None
    rating: float | None = None
    view_count: int = 0
    watched: bool = False
    last_viewed_at: int | None = None  # unix seconds
    added_at: int | None = None  # unix seconds
    library: str | None = None


class Person(BaseModel):
    name: str
    role: str | None = None


class ItemDetail(BaseModel):
    rating_key: str
    title: str
    type: str
    year: int | None = None
    summary: str | None = None
    tagline: str | None = None
    content_rating: str | None = None
    duration_ms: int | None = None
    user_rating: float | None = None
    audience_rating: float | None = None
    genres: list[str] = Field(default_factory=list)
    directors: list[str] = Field(default_factory=list)
    writers: list[str] = Field(default_factory=list)
    actors: list[Person] = Field(default_factory=list)
    studio: str | None = None
    originally_available_at: str | None = None
    added_at: int | None = None
    last_viewed_at: int | None = None
    view_count: int = 0
    watched: bool = False
    file_paths: list[str] = Field(default_factory=list)

    # Pre-formatted strings ready to drop into a note.
    genres_formatted: str = ""          # "Horror, Sci-Fi"
    directors_formatted: str = ""       # "John Carpenter"
    writers_formatted: str = ""
    actors_formatted: str = ""          # "Kurt Russell (MacReady), Wilford Brimley (Blair)"
    duration_formatted: str = ""        # "109 min"


class SearchCandidate(BaseModel):
    rating_key: str
    title: str
    type: str
    year: int | None = None
    library: str | None = None
    score: float  # 0.0 - 100.0, higher is better


class PosterSaveResult(BaseModel):
    rating_key: str
    title: str
    year: int | None = None
    path: str
    bytes_written: int
