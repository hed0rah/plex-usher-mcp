# plex-usher-mcp

A FastMCP server that exposes a Plex Media Server as a set of focused, read-only tools. Designed to be called by an LLM (Claude Code, via MCP) to answer natural-language queries about a Plex library — list items, fetch metadata, pull posters.

Built as the backend for a `#plex` tag in an Obsidian vault, but has zero knowledge of Obsidian. Any MCP client works.

## Install

Requires Python 3.11+ and network access to your Plex server.

```powershell
git clone https://github.com/hed0rah/plex-usher-mcp.git
cd plex-usher-mcp
python -m venv .venv
.\.venv\Scripts\Activate.ps1
pip install -e .
```

## Configure

Two env vars. Either export them in your shell or drop them in the platform config file:

- Windows: `%APPDATA%\plex-usher-mcp\.env`
- Linux: `~/.config/plex-usher-mcp/.env`
- macOS: `~/Library/Application Support/plex-usher-mcp/.env`

```env
PLEX_ADDRESS=https://192.0.2.2:32400
X_PLEX_TOKEN=your_plex_token
```

Getting the token: read `PlexOnlineToken` from the Plex server's `Preferences.xml`, or grab it from the `X-Plex-Token` query param on any authenticated request in the Plex web UI.

## Smoke test

```powershell
python scripts\smoke.py --stats
python scripts\smoke.py --query "Pulp Fiction"
python scripts\smoke.py --poster "Akira" --out .\akira.jpg
```

## Register with Claude Code

```powershell
claude mcp add plex-usher --scope user -- C:\path\to\plex-usher-mcp\.venv\Scripts\plex-usher-mcp.exe
```

Restart your Claude Code session to pick up the server.

## Tools

All read-only. All prefixed `plex_`.

| Tool | Purpose |
|---|---|
| `plex_list_libraries` | All library sections with key, title, type |
| `plex_library_stats` | Total + unwatched count for a section |
| `plex_list_items` | Paginated items in a section, with filters: `unwatched`, `genre`, `year_min/max`, `rating_min` |
| `plex_get_item` | Full metadata (structured + pre-formatted strings for actors, genres, etc.) |
| `plex_list_seasons` | Seasons for a show |
| `plex_list_episodes` | Episodes in a season |
| `plex_recently_added` | Recently added items across all libraries |
| `plex_on_deck` | Continue-watching list |
| `plex_search` | Fuzzy search (rapidfuzz-scored), top-N candidates with library section |
| `plex_get_poster` | Poster image returned as MCP `Image` content. Pure read — no disk writes |
| `plex_save_poster` | Fetches poster and writes it to `save_to` (absolute path on the MCP server's host). Returns path + byte count, no inline image. For clients that can't persist binary MCP content themselves |

## Design notes

- Tools are atomic. No markdown-formatting tools, no export-and-write-a-file tools. The calling model composes output.
- Two poster tools, clean separation of concerns. `plex_get_poster` is strictly read-only and returns MCP `Image` content — any client that can persist binary MCP content uses this. `plex_save_poster` takes an absolute `save_to` path and writes the file on the server's filesystem — escape hatch for clients (e.g. text-only Write tools) that can't handle binary content themselves. Splitting them lets MCP tool annotations be honest: `plex_get_poster` is `readOnly` + `idempotent`, `plex_save_poster` is non-read, `destructive` (overwrites on existing path), `idempotent`.
- All tools carry MCP annotations (`readOnlyHint`, `destructiveHint`, `idempotentHint`, `openWorldHint`) so clients can reason about what's safe to call repeatedly, what modifies state, and what might return different results over time.
- `plex_search` returns candidates with scores so the model can disambiguate fuzzy titles (e.g. "Aliens 2") and pick the intended `rating_key` before calling detail tools.
- `plex_get_item` returns pre-formatted strings (`actors_formatted`, `genres_formatted`, `duration_formatted`) alongside structured arrays so the caller can drop text into a note without spending tokens on formatting.

## License

MIT
