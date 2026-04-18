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
| `plex_get_poster` | Poster image returned as MCP `Image` content — caller saves it |

## Design notes

- Tools are atomic. No markdown-formatting tools, no export-and-write-a-file tools. The calling model composes output.
- `plex_get_poster` returns image content, not a filepath. The server has no "vault" concept and writes nothing to disk.
- `plex_search` returns candidates with scores so the model can disambiguate fuzzy titles (e.g. "Aliens 2") and pick the intended `rating_key` before calling detail tools.
- `plex_get_item` returns pre-formatted strings (`actors_formatted`, `genres_formatted`, `duration_formatted`) alongside structured arrays so the caller can drop text into a note without spending tokens on formatting.

## License

MIT
