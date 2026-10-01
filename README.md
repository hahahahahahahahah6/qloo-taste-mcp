# qloo-taste-mcp

An MCP server that wraps the [Qloo](https://www.qloo.com) Taste API — 250M+ cultural entities across music, movies, restaurants, brands, destinations, and more — as tools any AI agent can call. Plus a live web demo.

Built for the [Qloo Agentic Hackathon](https://qloo.devpost.com) (deadline Oct 30, 2026).

## What it does

Any MCP-compatible agent (Claude Code, etc.) gets four tools:

| Tool | What it does |
|---|---|
| `qloo_search` | Search the taste graph for entities ("Taylor Swift", "ramen") → entity IDs |
| `qloo_recommend` | Taste-based recommendations seeded by entity IDs (movies, restaurants, brands…) |
| `qloo_trending` | Currently trending entities in a category |
| `qloo_tags` | Search Qloo's tag taxonomy (genres, cuisines, travel themes) |

Example agent flow: "I love Taylor Swift and Wes Anderson films — find me a restaurant in LA" → `qloo_search` for the seeds → `qloo_recommend` with `urn:entity:restaurant`.

## Run the MCP server

Zero third-party dependencies — Python 3.10+ stdlib only.

```bash
export QLOO_API_KEY=<your key>   # free at https://www.qloo.com
python3 -m qloo_taste_mcp.server
```

Speaks MCP `2025-11-25` over newline-delimited JSON-RPC on stdio. With Claude Code, add to `.mcp.json`:

```json
{
  "mcpServers": {
    "qloo": { "command": "python3", "args": ["-m", "qloo_taste_mcp.server"],
              "env": { "QLOO_API_KEY": "<your key>" } }
  }
}
```

Without a key, tools return a helpful error instead of crashing.

## Live demo: Taste Match

`demo/` is a minimal web app: search things you like, pick a category, get Qloo-powered recommendations. The API key never leaves the server.

```bash
QLOO_API_KEY=<your key> python3 demo/app.py 8000
# open http://localhost:8000
```

## Tests

```bash
python3 -m unittest discover -s tests -v   # 15 tests, all HTTP mocked
```

## License

MIT
