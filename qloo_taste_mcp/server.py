"""qloo-taste-mcp: stdio MCP server wrapping the Qloo Taste API.

Speaks MCP 2025-11-25 over newline-delimited JSON-RPC on stdio.
Zero third-party dependencies.

Run:
    QLOO_API_KEY=<key> python3 -m qloo_taste_mcp.server
"""

from __future__ import annotations

import json
import sys

from qloo_taste_mcp import qloo

PROTOCOL_VERSION = "2025-11-25"
SERVER_NAME = "qloo-taste-mcp"
SERVER_VERSION = "0.1.0"

PARSE_ERROR = -32700
INVALID_REQUEST = -32600
METHOD_NOT_FOUND = -32601
INVALID_PARAMS = -32602
INTERNAL_ERROR = -32603

TOOL_DEFINITIONS = [
    {
        "name": "qloo_search",
        "description": (
            "Search Qloo's taste graph (250M+ entities: music, movies, restaurants, "
            "brands, destinations...) for entities matching a text query. Returns "
            "entity_ids you can feed into qloo_recommend."
        ),
        "inputSchema": {
            "type": "object",
            "properties": {
                "query": {"type": "string", "description": "Text to search for, e.g. 'Taylor Swift' or 'ramen'."},
                "types": {
                    "type": "array",
                    "items": {"type": "string"},
                    "description": "Optional entity-type URNs to restrict to, e.g. ['urn:entity:artist'].",
                },
                "take": {"type": "integer", "description": "Max results (1-50).", "default": 10},
            },
            "required": ["query"],
        },
        "annotations": {"readOnlyHint": True, "destructiveHint": False, "openWorldHint": True},
    },
    {
        "name": "qloo_recommend",
        "description": (
            "Get taste-based recommendations from Qloo's cultural AI, seeded by "
            "entity IDs (from qloo_search). E.g. seed with a favorite artist, get "
            "back movies, restaurants, or brands the same taste profile enjoys."
        ),
        "inputSchema": {
            "type": "object",
            "properties": {
                "entity_ids": {
                    "type": "array",
                    "items": {"type": "string"},
                    "description": "Seed entity IDs from qloo_search.",
                },
                "result_type": {
                    "type": "string",
                    "description": "Entity-type URN to recommend, e.g. 'urn:entity:movie', 'urn:entity:restaurant', 'urn:entity:brand', 'urn:entity:artist'.",
                },
                "take": {"type": "integer", "description": "Max results (1-50).", "default": 10},
            },
            "required": ["entity_ids", "result_type"],
        },
        "annotations": {"readOnlyHint": True, "destructiveHint": False, "openWorldHint": True},
    },
    {
        "name": "qloo_trending",
        "description": "Currently trending entities within a category, e.g. trending brands or movies.",
        "inputSchema": {
            "type": "object",
            "properties": {
                "entity_type": {
                    "type": "string",
                    "description": "Category URN, e.g. 'urn:entity:brand', 'urn:entity:movie', 'urn:entity:tv_show'.",
                },
                "take": {"type": "integer", "description": "Max results (1-50).", "default": 10},
            },
            "required": ["entity_type"],
        },
        "annotations": {"readOnlyHint": True, "destructiveHint": False, "openWorldHint": True},
    },
    {
        "name": "qloo_tags",
        "description": "Search Qloo's tag taxonomy (genres, cuisines, travel themes...) for tag IDs usable in filters.",
        "inputSchema": {
            "type": "object",
            "properties": {
                "term": {"type": "string", "description": "Term to search, e.g. 'jazz' or 'beach'."},
                "take": {"type": "integer", "description": "Max results (1-50).", "default": 10},
            },
            "required": ["term"],
        },
        "annotations": {"readOnlyHint": True, "destructiveHint": False, "openWorldHint": True},
    },
]


def _ok(msg_id, result):
    return {"jsonrpc": "2.0", "id": msg_id, "result": result}


def _err(msg_id, code, message):
    return {"jsonrpc": "2.0", "id": msg_id, "error": {"code": code, "message": message}}


def call_tool(name: str, arguments: dict) -> tuple[str, bool]:
    """Run a tool. Returns (text, is_error)."""
    try:
        if name == "qloo_search":
            out = qloo.search_entities(
                arguments["query"],
                types=arguments.get("types"),
                take=arguments.get("take", 10),
            )
        elif name == "qloo_recommend":
            out = qloo.recommend(
                arguments["entity_ids"],
                arguments["result_type"],
                take=arguments.get("take", 10),
            )
        elif name == "qloo_trending":
            out = qloo.trending(arguments["entity_type"], take=arguments.get("take", 10))
        elif name == "qloo_tags":
            out = qloo.search_tags(arguments["term"], take=arguments.get("take", 10))
        else:
            return f"Unknown tool: {name}", True
        return json.dumps(out, indent=2, ensure_ascii=False), False
    except KeyError as e:
        return f"Missing required argument: {e}", True
    except qloo.QlooError as e:
        return str(e), True
    except Exception as e:  # never crash the session on a tool failure
        return f"Tool failed: {type(e).__name__}: {e}", True


def handle(msg: dict):
    if not isinstance(msg, dict) or msg.get("jsonrpc") != "2.0":
        return _err(None, INVALID_REQUEST, "Invalid JSON-RPC 2.0 message.")
    method = msg.get("method")
    msg_id = msg.get("id")
    params = msg.get("params") or {}
    if not isinstance(method, str):
        return _err(msg_id, INVALID_REQUEST, "Missing 'method'.")
    if not isinstance(params, dict):
        return _err(msg_id, INVALID_PARAMS, "'params' must be an object.")

    if method == "initialize":
        return _ok(msg_id, {
            "protocolVersion": PROTOCOL_VERSION,
            "capabilities": {"tools": {"listChanged": False}},
            "serverInfo": {"name": SERVER_NAME, "version": SERVER_VERSION},
        })
    if method in ("notifications/initialized",):
        return None
    if method == "ping":
        return _ok(msg_id, {})
    if method == "tools/list":
        return _ok(msg_id, {"tools": TOOL_DEFINITIONS})
    if method == "tools/call":
        name = params.get("name")
        arguments = params.get("arguments") or {}
        if not isinstance(name, str):
            return _err(msg_id, INVALID_PARAMS, "Missing 'name' for tools/call.")
        if not isinstance(arguments, dict):
            return _err(msg_id, INVALID_PARAMS, "'arguments' must be an object.")
        text, is_error = call_tool(name, arguments)
        return _ok(msg_id, {
            "content": [{"type": "text", "text": text}],
            "isError": is_error,
        })
    if "id" not in msg:  # unknown notification: ignore
        return None
    return _err(msg_id, METHOD_NOT_FOUND, f"Unknown method: {method}.")


def main() -> None:
    stdin = sys.stdin
    stdout = sys.stdout
    for line in stdin:
        line = line.strip()
        if not line:
            continue
        try:
            msg = json.loads(line)
        except json.JSONDecodeError:
            resp = _err(None, PARSE_ERROR, "Invalid JSON.")
            stdout.write(json.dumps(resp) + "\n")
            stdout.flush()
            continue
        resp = handle(msg)
        if resp is not None:
            stdout.write(json.dumps(resp, ensure_ascii=False) + "\n")
            stdout.flush()


if __name__ == "__main__":
    main()
