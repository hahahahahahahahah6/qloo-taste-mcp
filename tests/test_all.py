"""Tests for qloo-taste-mcp. All HTTP is mocked; no real API calls, no key needed."""

import io
import json
import os
import sys
import unittest
from unittest.mock import patch

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

from qloo_taste_mcp import qloo, server


FAKE_SEARCH = {
    "results": [
        {
            "name": "Taylor Swift",
            "entity_id": "urn:entity:artist:taylorswift",
            "types": ["urn:entity:artist"],
            "popularity": 0.99,
            "properties": {"description": "American singer-songwriter."},
        },
        {
            "name": "Taylor's Coffee",
            "entity_id": "urn:entity:place:123",
            "types": ["urn:entity:place"],
            "popularity": 0.12,
        },
    ]
}


class FakeResp:
    def __init__(self, payload):
        self._payload = json.dumps(payload).encode()

    def read(self):
        return self._payload

    def __enter__(self):
        return self

    def __exit__(self, *a):
        return False


def fake_urlopen_factory(payload):
    def _fake(req, timeout=30):
        _fake.last_url = req.full_url
        _fake.last_key = req.headers.get("X-api-key") or req.headers.get("X-Api-Key")
        return FakeResp(payload)
    return _fake


class QlooClientTests(unittest.TestCase):
    def setUp(self):
        os.environ["QLOO_API_KEY"] = "test-key"

    def tearDown(self):
        os.environ.pop("QLOO_API_KEY", None)

    def test_missing_key_raises_helpful_error(self):
        os.environ.pop("QLOO_API_KEY", None)
        with self.assertRaises(qloo.QlooError) as cm:
            qloo.search_entities("x")
        self.assertIn("QLOO_API_KEY", str(cm.exception))

    def test_search_compacts_entities(self):
        fake = fake_urlopen_factory(FAKE_SEARCH)
        with patch("urllib.request.urlopen", fake):
            out = qloo.search_entities("taylor", take=5)
        self.assertEqual(len(out), 2)
        self.assertEqual(out[0]["name"], "Taylor Swift")
        self.assertEqual(out[0]["entity_id"], "urn:entity:artist:taylorswift")
        self.assertIn("description", out[0])
        self.assertNotIn("description", out[1])  # compact: no empty fields
        self.assertIn("query=taylor", fake.last_url)
        self.assertIn("take=5", fake.last_url)

    def test_search_types_param(self):
        fake = fake_urlopen_factory(FAKE_SEARCH)
        with patch("urllib.request.urlopen", fake):
            qloo.search_entities("ramen", types=["urn:entity:restaurant"])
        self.assertIn("urn%3Aentity%3Arestaurant", fake.last_url)

    def test_recommend_builds_insights_query(self):
        fake = fake_urlopen_factory({"results": []})
        with patch("urllib.request.urlopen", fake):
            qloo.recommend(["urn:entity:artist:taylorswift"], "urn:entity:movie", take=3)
        self.assertIn("/v2/insights", fake.last_url)
        self.assertIn("filter.type=urn%3Aentity%3Amovie", fake.last_url)
        self.assertIn("signal.interests.entities=", fake.last_url)

    def test_recommend_needs_seed(self):
        with self.assertRaises(qloo.QlooError):
            qloo.recommend([], "urn:entity:movie")

    def test_trending_hits_category_endpoint(self):
        fake = fake_urlopen_factory({"results": []})
        with patch("urllib.request.urlopen", fake):
            qloo.trending("urn:entity:brand", take=7)
        self.assertIn("/trends/category", fake.last_url)
        self.assertIn("type=urn%3Aentity%3Abrand", fake.last_url)

    def test_tags(self):
        fake = fake_urlopen_factory({"results": [{"name": "jazz", "tag_id": "urn:tag:genre:jazz", "types": []}]})
        with patch("urllib.request.urlopen", fake):
            out = qloo.search_tags("jazz")
        self.assertEqual(out[0]["tag_id"], "urn:tag:genre:jazz")
        self.assertIn("/v2/tags", fake.last_url)


class ServerProtocolTests(unittest.TestCase):
    def test_initialize(self):
        resp = server.handle({"jsonrpc": "2.0", "id": 1, "method": "initialize", "params": {}})
        self.assertEqual(resp["result"]["protocolVersion"], "2025-11-25")
        self.assertIn("tools", resp["result"]["capabilities"])

    def test_tools_list_has_four_tools(self):
        resp = server.handle({"jsonrpc": "2.0", "id": 2, "method": "tools/list"})
        names = [t["name"] for t in resp["result"]["tools"]]
        self.assertEqual(names, ["qloo_search", "qloo_recommend", "qloo_trending", "qloo_tags"])

    def test_tools_call_search(self):
        os.environ["QLOO_API_KEY"] = "test-key"
        fake = fake_urlopen_factory(FAKE_SEARCH)
        with patch("urllib.request.urlopen", fake):
            resp = server.handle({
                "jsonrpc": "2.0", "id": 3, "method": "tools/call",
                "params": {"name": "qloo_search", "arguments": {"query": "taylor"}},
            })
        content = resp["result"]["content"][0]["text"]
        self.assertIn("Taylor Swift", content)
        self.assertFalse(resp["result"]["isError"])
        os.environ.pop("QLOO_API_KEY", None)

    def test_tools_call_unknown_tool_is_error_not_crash(self):
        resp = server.handle({
            "jsonrpc": "2.0", "id": 4, "method": "tools/call",
            "params": {"name": "nope", "arguments": {}},
        })
        self.assertTrue(resp["result"]["isError"])

    def test_tools_call_missing_key_is_error_text(self):
        os.environ.pop("QLOO_API_KEY", None)
        resp = server.handle({
            "jsonrpc": "2.0", "id": 5, "method": "tools/call",
            "params": {"name": "qloo_trending", "arguments": {"entity_type": "urn:entity:brand"}},
        })
        self.assertTrue(resp["result"]["isError"])
        self.assertIn("QLOO_API_KEY", resp["result"]["content"][0]["text"])

    def test_unknown_method(self):
        resp = server.handle({"jsonrpc": "2.0", "id": 6, "method": "frobnicate"})
        self.assertEqual(resp["error"]["code"], -32601)

    def test_notification_returns_none(self):
        self.assertIsNone(server.handle({"jsonrpc": "2.0", "method": "notifications/initialized"}))

    def test_ping(self):
        resp = server.handle({"jsonrpc": "2.0", "id": 7, "method": "ping"})
        self.assertEqual(resp["result"], {})


if __name__ == "__main__":
    unittest.main()
