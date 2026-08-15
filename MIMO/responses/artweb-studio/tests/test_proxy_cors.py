"""Unit tests for playground_proxy CORS + payload guards (no network)."""
import sys
from pathlib import Path

import pytest

SRC_DIR = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(SRC_DIR))

import playground_proxy as pp  # noqa: E402


def test_cors_localhost_allowlist():
    class Probe(pp.H):
        def __init__(self, origin):
            self._sent = []
            self.headers = {"Origin": origin} if origin else {}

        def send_header(self, k, v):
            self._sent.append((k, v))

    # Sanity: localhost in allowlist, hostile + wildcard out.
    assert "http://localhost:3000" in pp.ALLOWED_ORIGINS
    assert "https://evil.example.com" not in pp.ALLOWED_ORIGINS
    assert "*" not in pp.ALLOWED_ORIGINS

    # Hostile Origin: no ACAO header at all.
    h = Probe("https://evil.example.com")
    h._cors()
    assert all(k != "Access-Control-Allow-Origin" for k, _ in h._sent)

    # Localhost Origin reflected with Vary: Origin.
    h = Probe("http://localhost:3000")
    h._cors()
    assert ("Access-Control-Allow-Origin", "http://localhost:3000") in h._sent
    assert ("Vary", "Origin") in h._sent


def test_do_post_rejects_non_object():
    class Req:
        def __init__(self, body):
            self.body = body

    class Probe(pp.H):
        def __init__(self, body):
            self._resp = None
            self._body = body

        def _json(self, obj, code=200):
            self._resp = (code, obj)

    # body cap guard triggers on oversized Content-Length
    p = Probe(b"{}")
    p.headers = {"Content-Length": "2000000"}
    p.rfile = None
    # do_POST reads Content-Length first and 413s before touching rfile
    p.do_POST()
    assert p._resp[0] == 413
    assert "payload too large" in p._resp[1]["error"]
