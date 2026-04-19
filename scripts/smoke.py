"""End-to-end smoke test against the configured Plex server.

Exercises the same code paths the MCP tools use, without the MCP transport.
Run from the repo root after `pip install -e .`:

    python scripts/smoke.py
    python scripts/smoke.py --stats
    python scripts/smoke.py --query "Pulp Fiction"
    python scripts/smoke.py --poster "Pulp Fiction" --out ./poster.jpg
"""

from __future__ import annotations

import argparse
import asyncio
import sys
from pathlib import Path

from plex_usher.client import PlexClient
from plex_usher.config import Config
from plex_usher.utils import (
    parse_item_detail,
    parse_item_summary,
    parse_library,
    parse_library_stats,
)


async def run(query: str | None, poster: str | None, out: Path | None, show_stats: bool) -> int:
    config = Config.from_env()
    print(f"[config] address={config.plex_address}  token=***{config.plex_token[-4:]}")
    print()

    client = PlexClient(config)
    try:
        raw = await client.get_json("/library/sections/all")
        libs = [parse_library(d) for d in raw.get("MediaContainer", {}).get("Directory", [])]
        print(f"[libraries] {len(libs)} sections")
        for lib in libs:
            print(f"  - key={lib.key:>3}  type={lib.type:<8}  title={lib.title}")
        print()

        if show_stats:
            print("[stats]")
            for lib in libs:
                total_raw = await client.get_json(
                    f"/library/sections/{lib.key}/all",
                    params={"X-Plex-Container-Start": 0, "X-Plex-Container-Size": 0},
                )
                total = int(total_raw.get("MediaContainer", {}).get("totalSize", 0)) or len(
                    total_raw.get("MediaContainer", {}).get("Metadata", []) or []
                )
                unwatched: int | None = None
                if lib.type in {"movie", "show"}:
                    uw_raw = await client.get_json(
                        f"/library/sections/{lib.key}/all",
                        params={
                            "unwatched": 1,
                            "X-Plex-Container-Start": 0,
                            "X-Plex-Container-Size": 0,
                        },
                    )
                    unwatched = int(uw_raw.get("MediaContainer", {}).get("totalSize", 0)) or len(
                        uw_raw.get("MediaContainer", {}).get("Metadata", []) or []
                    )
                stats = parse_library_stats(lib, total, unwatched)
                unwatched_str = f"{stats.unwatched_count} unwatched" if stats.unwatched_count is not None else "-"
                print(f"  - {stats.title:<22} total={stats.total_count:<5} {unwatched_str}")
            print()

        search_term = query or poster
        if not search_term:
            return 0

        print(f"[search] query={search_term!r}")
        raw = await client.get_json("/search", params={"query": search_term})
        results = raw.get("MediaContainer", {}).get("Metadata", []) or []
        if not results:
            print("  (no results)")
            return 1

        for m in results[:5]:
            rk = m.get("ratingKey")
            title = m.get("title")
            year = m.get("year")
            typ = m.get("type")
            lib = m.get("librarySectionTitle")
            print(f"  - ratingKey={rk}  type={typ:<8}  {title} ({year})  [{lib}]")

        top = results[0]
        top_rk = str(top["ratingKey"])
        print()
        print(f"[get_item] rating_key={top_rk}")
        raw = await client.get_json(f"/library/metadata/{top_rk}")
        items = raw.get("MediaContainer", {}).get("Metadata", []) or []
        if not items:
            print("  (no metadata)")
            return 1
        detail = parse_item_detail(items[0])
        print(f"  title: {detail.title} ({detail.year})  type={detail.type}")
        print(f"  watched: {detail.watched} (views={detail.view_count})  duration: {detail.duration_formatted}")
        if detail.genres_formatted:
            print(f"  genres: {detail.genres_formatted}")
        if detail.directors_formatted:
            print(f"  directors: {detail.directors_formatted}")
        if detail.actors_formatted:
            print(f"  actors: {detail.actors_formatted}")
        if detail.file_paths:
            print(f"  files: {detail.file_paths[0]}")
        print()

        if poster:
            thumb = items[0].get("thumb")
            if not thumb:
                print(f"[poster] no thumb for {detail.title}")
                return 1
            data, content_type = await client.stream_image(thumb)
            # extension from content_type ("image/png" -> "png"); default to jpg
            ext = content_type.split("/", 1)[1] if "/" in content_type else "jpg"
            dest = out or Path(f"./poster-{detail.rating_key}.{ext}")
            dest.parent.mkdir(parents=True, exist_ok=True)
            dest.write_bytes(data)
            print(f"[poster] wrote {len(data):,} bytes ({content_type}) -> {dest}")

        return 0
    finally:
        await client.aclose()


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--query", help="search term; show top 5 and fetch detail for the first hit")
    parser.add_argument("--poster", help="search term; as --query, plus download the poster to --out")
    parser.add_argument("--out", type=Path, help="output file for --poster (default: ./poster-<ratingKey>.jpg)")
    parser.add_argument("--stats", action="store_true", help="show per-library total/unwatched counts")
    args = parser.parse_args()
    sys.exit(asyncio.run(run(args.query, args.poster, args.out, args.stats)))


if __name__ == "__main__":
    main()
