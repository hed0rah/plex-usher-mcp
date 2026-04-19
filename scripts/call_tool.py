"""Invoke a registered MCP tool by name from the CLI.

Goes through FastMCP's in-process Client, exercising the same registry the
stdio transport hits. Closer to a real cowork/noggin call than smoke.py.

Usage:
    python scripts/call_tool.py --list
    python scripts/call_tool.py plex_list_libraries
    python scripts/call_tool.py plex_search query=Aliens limit=5
    python scripts/call_tool.py plex_list_items section_key=1 unwatched=true year_min=1980
    python scripts/call_tool.py plex_save_poster rating_key=12345 save_to=/tmp/p.jpg

Argument coercion: true/false -> bool, all-digits -> int, numeric with dot
-> float, anything else -> str. Use --json '{...}' for nested values.
"""

from __future__ import annotations

import argparse
import asyncio
import json
import sys
from typing import Any

from fastmcp import Client

from plex_usher.server import mcp


def _coerce(value: str) -> Any:
    lowered = value.lower()
    if lowered in {"true", "false"}:
        return lowered == "true"
    if value.lstrip("-").isdigit():
        return int(value)
    try:
        return float(value)
    except ValueError:
        return value


def _parse_kwargs(pairs: list[str]) -> dict[str, Any]:
    out: dict[str, Any] = {}
    for pair in pairs:
        if "=" not in pair:
            raise SystemExit(f"bad arg {pair!r}: expected key=value")
        key, _, raw = pair.partition("=")
        out[key] = _coerce(raw)
    return out


def _print_result(result: Any) -> None:
    # FastMCP Client returns a CallToolResult with .data (structured) and .content (blocks)
    data = getattr(result, "data", None)
    if data is not None:
        if hasattr(data, "model_dump"):
            print(json.dumps(data.model_dump(), indent=2, default=str))
        elif isinstance(data, list) and data and hasattr(data[0], "model_dump"):
            print(json.dumps([d.model_dump() for d in data], indent=2, default=str))
        else:
            print(json.dumps(data, indent=2, default=str))
        return

    for block in getattr(result, "content", []) or []:
        kind = type(block).__name__
        if hasattr(block, "data"):
            mime = getattr(block, "mimeType", "?")
            print(f"[{kind}] {mime}, {len(block.data)} bytes")
        else:
            print(f"[{kind}] {block}")


async def _run(tool: str | None, kwargs: dict[str, Any], list_only: bool, json_args: str | None) -> int:
    if json_args:
        kwargs = {**json.loads(json_args), **kwargs}

    async with Client(mcp) as client:
        if list_only or tool is None:
            tools = await client.list_tools()
            for t in tools:
                print(f"  {t.name}")
            return 0

        result = await client.call_tool(tool, kwargs)
        if getattr(result, "is_error", False):
            print(f"[error] {result.content}", file=sys.stderr)
            return 1
        _print_result(result)
        return 0


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("tool", nargs="?", help="tool name (omit with --list)")
    parser.add_argument("kwargs", nargs="*", help="key=value pairs")
    parser.add_argument("--list", action="store_true", help="list registered tools and exit")
    parser.add_argument("--json", help="JSON object of args (merged with key=value)")
    args = parser.parse_args()

    sys.exit(asyncio.run(_run(args.tool, _parse_kwargs(args.kwargs), args.list, args.json)))


if __name__ == "__main__":
    main()
