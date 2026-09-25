"""Interactive, replay-first local AgentFire dashboard."""
from __future__ import annotations

import json
import os
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path

from dotenv import load_dotenv

from dashboard_data import build_dashboard_data
from providers.nimble import NimbleProvider
from providers.rawtree import RawTreeEventBackend
from verified_replay_cache import CACHE

load_dotenv()
HTML_PATH = Path(__file__).with_name("dashboard.html")


def load_dashboard_data():
    """Prefer live RawTree telemetry; fall back only to the verified replay cache."""
    try:
        try:
            nimble_status = NimbleProvider().status.state
        except Exception:
            nimble_status = "NOT_CONFIGURED"
        return build_dashboard_data(RawTreeEventBackend(), nimble_status)
    except Exception:
        return CACHE


class DashboardHandler(BaseHTTPRequestHandler):
    def do_GET(self):
        if self.path == "/api/data":
            body = json.dumps(load_dashboard_data()).encode("utf-8")
            self.send_response(200)
            self.send_header("Content-Type", "application/json; charset=utf-8")
            self.send_header("Cache-Control", "no-store")
            self.end_headers()
            self.wfile.write(body)
            return
        if self.path not in ("/", "/index.html"):
            self.send_error(404)
            return
        body = HTML_PATH.read_bytes()
        self.send_response(200)
        self.send_header("Content-Type", "text/html; charset=utf-8")
        self.end_headers()
        self.wfile.write(body)

    def log_message(self, *_):
        pass


if __name__ == "__main__":
    port = int(os.getenv("AGENTFIRE_DASHBOARD_PORT", "8787"))
    print(f"AgentFire dashboard: http://127.0.0.1:{port}")
    ThreadingHTTPServer(("127.0.0.1", port), DashboardHandler).serve_forever()
