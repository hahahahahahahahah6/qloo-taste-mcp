"""Taste Match demo backend (stdlib only).

Serves the demo page and proxies browser requests to the Qloo API so the
API key never leaves the server.

Run:
    QLOO_API_KEY=<key> python3 demo/app.py [port]
Then open http://localhost:8000
"""

from __future__ import annotations

import json
import os
import sys
import urllib.parse
from http.server import BaseHTTPRequestHandler, HTTPServer

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

from qloo_taste_mcp import qloo

HERE = os.path.dirname(os.path.abspath(__file__))

RESULT_TYPES = {
    "movies": "urn:entity:movie",
    "tv shows": "urn:entity:tv_show",
    "music artists": "urn:entity:artist",
    "restaurants": "urn:entity:restaurant",
    "brands": "urn:entity:brand",
    "destinations": "urn:entity:destination",
}


class Handler(BaseHTTPRequestHandler):
    server_version = "TasteMatch/0.1"

    def _json(self, obj, status=200):
        body = json.dumps(obj, ensure_ascii=False).encode()
        self.send_response(status)
        self.send_header("Content-Type", "application/json; charset=utf-8")
        self.send_header("Content-Length", str(len(body)))
        self.end_headers()
        self.wfile.write(body)

    def _page(self):
        path = os.path.join(HERE, "index.html")
        with open(path, "rb") as f:
            body = f.read()
        self.send_response(200)
        self.send_header("Content-Type", "text/html; charset=utf-8")
        self.send_header("Content-Length", str(len(body)))
        self.end_headers()
        self.wfile.write(body)

    def do_GET(self):
        parsed = urllib.parse.urlparse(self.path)
        if parsed.path == "/":
            return self._page()
        if parsed.path == "/api/result-types":
            return self._json(sorted(RESULT_TYPES.keys()))
        if parsed.path == "/api/search":
            q = urllib.parse.parse_qs(parsed.query).get("q", [""])[0]
            if not q.strip():
                return self._json({"error": "missing q"}, 400)
            try:
                return self._json({"results": qloo.search_entities(q.strip(), take=8)})
            except qloo.QlooError as e:
                return self._json({"error": str(e)}, 502)
        self.send_response(404)
        self.end_headers()

    def do_POST(self):
        parsed = urllib.parse.urlparse(self.path)
        if parsed.path != "/api/recommend":
            self.send_response(404)
            self.end_headers()
            return
        try:
            length = int(self.headers.get("Content-Length", 0))
            payload = json.loads(self.rfile.read(length).decode() or "{}")
        except Exception:
            return self._json({"error": "invalid JSON body"}, 400)
        seeds = payload.get("seeds") or []
        want = payload.get("want", "")
        result_type = RESULT_TYPES.get(want)
        if not seeds:
            return self._json({"error": "pick at least one seed first"}, 400)
        if not result_type:
            return self._json({"error": f"unknown category {want!r}"}, 400)
        try:
            recs = qloo.recommend(seeds, result_type, take=12)
        except qloo.QlooError as e:
            return self._json({"error": str(e)}, 502)
        # never recommend something the user already seeded
        seed_set = set(seeds)
        recs = [r for r in recs if r.get("entity_id") not in seed_set]
        return self._json({"results": recs})

    def log_message(self, fmt, *args):  # quieter logs
        sys.stderr.write("taste-match: " + fmt % args + "\n")


def main():
    port = int(sys.argv[1]) if len(sys.argv) > 1 else int(os.environ.get("PORT", "8000"))
    try:
        qloo._api_key()
    except qloo.QlooError as e:
        sys.stderr.write(f"taste-match: warning: {e}\n")
    srv = HTTPServer(("0.0.0.0", port), Handler)
    print(f"Taste Match demo on http://localhost:{port} (set QLOO_API_KEY first)")
    srv.serve_forever()


if __name__ == "__main__":
    main()
