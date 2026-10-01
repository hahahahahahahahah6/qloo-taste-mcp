"""Qloo Taste API client (stdlib only).

Reads the API key from the QLOO_API_KEY environment variable and the base URL
from QLOO_API_BASE (defaults to the hackathon environment).
Docs: https://docs.qloo.com (public mirror: github.com/qloo/docs-public)
"""

from __future__ import annotations

import json
import os
import urllib.parse
import urllib.request


DEFAULT_BASE = "https://hackathon.api.qloo.com"


class QlooError(Exception):
    """Raised when the Qloo API call fails or is misconfigured."""


def _api_key() -> str:
    key = os.environ.get("QLOO_API_KEY", "").strip()
    if not key:
        raise QlooError(
            "QLOO_API_KEY is not set. Get a free key at https://www.qloo.com "
            "(or the Qloo hackathon page) and export QLOO_API_KEY=<your key>."
        )
    return key


def _base() -> str:
    return os.environ.get("QLOO_API_BASE", DEFAULT_BASE).rstrip("/")


def _get(path: str, params: dict) -> dict:
    query = urllib.parse.urlencode(params, doseq=True)
    url = f"{_base()}{path}?{query}"
    req = urllib.request.Request(
        url,
        headers={"X-Api-Key": _api_key(), "accept": "application/json"},
        method="GET",
    )
    try:
        with urllib.request.urlopen(req, timeout=30) as resp:
            return json.loads(resp.read().decode("utf-8"))
    except urllib.error.HTTPError as e:
        try:
            body = e.read().decode("utf-8")[:500]
        except Exception:
            body = ""
        raise QlooError(f"Qloo API error {e.code}: {body}") from e
    except urllib.error.URLError as e:
        raise QlooError(f"Could not reach Qloo API: {e.reason}") from e


def _compact_entity(e: dict) -> dict:
    """Reduce a raw Qloo entity to the fields an agent actually needs."""
    out = {
        "name": e.get("name"),
        "entity_id": e.get("entity_id"),
        "types": e.get("types"),
        "popularity": e.get("popularity"),
    }
    props = e.get("properties") or {}
    desc = props.get("description") or props.get("short_description")
    if desc:
        out["description"] = str(desc)[:300]
    if e.get("location"):
        out["location"] = e.get("location")
    return {k: v for k, v in out.items() if v is not None}


def search_entities(query: str, types: list[str] | None = None, take: int = 10) -> list[dict]:
    """Search Qloo's taste graph for entities matching a text query."""
    params: dict = {"query": query, "take": max(1, min(take, 50))}
    if types:
        params["types"] = types
    data = _get("/search", params)
    return [_compact_entity(e) for e in data.get("results", [])]


def recommend(entity_ids: list[str], result_type: str, take: int = 10) -> list[dict]:
    """Get taste-based recommendations seeded by known entity IDs."""
    if not entity_ids:
        raise QlooError("recommend() needs at least one seed entity_id (use search_entities first).")
    params = {
        "filter.type": result_type,
        "signal.interests.entities": ",".join(entity_ids),
        "take": max(1, min(take, 50)),
    }
    data = _get("/v2/insights", params)
    return [_compact_entity(e) for e in data.get("results", [])]


def trending(entity_type: str, take: int = 10) -> list[dict]:
    """Currently trending entities within a category (e.g. urn:entity:brand)."""
    data = _get("/trends/category", {"type": entity_type, "take": max(1, min(take, 50))})
    return [_compact_entity(e) for e in data.get("results", [])]


def search_tags(term: str, take: int = 10) -> list[dict]:
    """Search Qloo's tag taxonomy (useful for building tag-based filters)."""
    data = _get("/v2/tags", {"term": term, "take": max(1, min(take, 50))})
    return [
        {"name": t.get("name"), "tag_id": t.get("tag_id"), "types": t.get("types")}
        for t in data.get("results", [])
    ]
