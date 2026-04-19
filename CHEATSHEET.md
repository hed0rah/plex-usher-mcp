# plex-usher CLI cheatsheet

Quick ways to drive the server outside cowork / noggin2.

## setup (once)

```bash
pip install -e .
```

Plex creds via env vars or `~/.config/plex-usher-mcp/.env` (Linux) /
`%APPDATA%\plex-usher-mcp\.env` (Windows):

```
PLEX_ADDRESS=https://192.0.2.10:32400
X_PLEX_TOKEN=xxxxxxxxxxxxxxxxxxxx
```

---

## scripts/call_tool.py — invoke any registered MCP tool

Goes through the same FastMCP registry the stdio transport uses. Closest thing
to a real tool call without spawning the server.

```bash
# list every registered tool
python scripts/call_tool.py --list

# zero-arg
python scripts/call_tool.py plex_list_libraries
python scripts/call_tool.py plex_on_deck

# key=value args (auto-coerced: true/false -> bool, digits -> int, x.y -> float)
python scripts/call_tool.py plex_library_stats section_key=1
python scripts/call_tool.py plex_search query=Aliens limit=5
python scripts/call_tool.py plex_list_items section_key=1 unwatched=true year_min=1980 limit=10
python scripts/call_tool.py plex_get_item rating_key=12345
python scripts/call_tool.py plex_save_poster rating_key=12345 save_to=/tmp/p.jpg

# nested / awkward values via JSON
python scripts/call_tool.py plex_list_items --json '{"section_key":"1","sort":"addedAt:desc"}'
```

Output: structured Pydantic results print as pretty JSON. Binary content (poster
bytes from `plex_get_poster`) prints as `[ImageContent] image/jpeg, 12345 bytes`.

---

## scripts/smoke.py — opinionated end-to-end probe

Bypasses the MCP layer entirely. Useful when you want to confirm the Plex
HTTP client works at all, or quickly inspect a top hit.

```bash
python scripts/smoke.py                         # list libraries
python scripts/smoke.py --stats                 # + per-library counts
python scripts/smoke.py --query "Pulp Fiction"  # search + detail of top hit
python scripts/smoke.py --poster "Pulp Fiction" --out ./poster.jpg
```

---

## fastmcp dev — MCP Inspector UI

For poking the server over the wire with a browser GUI:

```bash
fastmcp dev src/plex_usher/server.py:mcp
```

Opens MCP Inspector in your browser. Lets you fire any tool, see the raw
JSON-RPC, inspect annotations, etc. Slowest path, but the most "real".

---

## stdio transport — what cowork / noggin actually do

```bash
python -m plex_usher.server
```

Reads JSON-RPC on stdin, writes on stdout. Not human-friendly; use one of the
other paths unless you're debugging a transport-level issue.
