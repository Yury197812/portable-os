"""
playground_proxy.py — local CORS proxy for the ArtWeb Studio Playground.

Proxies OpenAI-compatible chat completions. Local providers (Ollama,
LM Studio) need no key and are the default; cloud providers (Groq,
OpenRouter free) are best-effort with server-side keys.

Endpoints:
  GET  /api/health   -> {ok, providers}
  GET  /api/models   -> model list
  POST /api/chat     -> {provider, model, messages, temperature} -> completion
"""
from __future__ import annotations

import json
import os
import sqlite3
import threading
import time
import urllib.error
import urllib.request
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from urllib.parse import parse_qs, urlparse

KEYS_PATH = Path(os.environ.get("ARTWEB_KEYS_PATH", r"D:\4\04_utilities\api_keys.json"))
SEED_DIR = Path(__file__).parent
PORT = int(os.environ.get("ARTWEB_PROXY_PORT", "8890"))
REVIEWS_DB = SEED_DIR / "reviews.db"
_DB_LOCK = threading.Lock()

# CORS: localhost-only allowlist. Never wildcard — a hostile origin must be
# rejected by the browser, not granted.
ALLOWED_ORIGINS = {
    "http://localhost:3000",
    "http://127.0.0.1:3000",
    "http://localhost:8890",
    "http://127.0.0.1:8890",
    "http://localhost:8891",
    "http://127.0.0.1:8891",
}

# base already ends in /v1 (OpenAI-compatible); auth=False = no key needed
PROVIDERS = {
    "ollama":          {"base": "http://127.0.0.1:11434/v1", "auth": False},
    "lmstudio":        {"base": "http://127.0.0.1:1234/v1", "auth": False},
    "groq":            {"base": "https://api.groq.com/openai/v1", "auth": True},
    "openrouter_free": {"base": "https://openrouter.ai/api/v1", "auth": True},
}

MODELS = [
    {"provider": "ollama", "id": "qwen2.5:14b", "name": "Qwen2.5 14B · Ollama", "caps": ["tool_use", "code", "free", "speed"]},
    {"provider": "groq", "id": "llama-3.3-70b-versatile", "name": "Llama 3.3 70B · Groq", "caps": ["tool_use", "reasoning"]},
    {"provider": "groq", "id": "llama-3.1-8b-instant", "name": "Llama 3.1 8B · Groq", "caps": ["tool_use", "speed"]},
    {"provider": "openrouter_free", "id": "openai/gpt-oss-20b:free", "name": "GPT-OSS 20B · OpenRouter", "caps": ["tool_use", "code"]},
    {"provider": "openrouter_free", "id": "google/gemma-4-26b-a4b-it:free", "name": "Gemma 4 26B · OpenRouter", "caps": ["tool_use"]},
    {"provider": "openrouter_free", "id": "liquid/lfm-2.5-2.6b:free", "name": "LFM 2.5 2.6B · OpenRouter", "caps": ["speed"]},
    {"provider": "openrouter_free", "id": "nvidia/nemotron-nano-9b-v2:free", "name": "Nemotron Nano 9B · OpenRouter", "caps": ["tool_use"]},
]


def load_keys():
    data = json.loads(KEYS_PATH.read_text(encoding="utf-8"))
    return {n: data.get(n, {}).get("api_key") for n in PROVIDERS if data.get(n, {}).get("api_key")}


def call_chat(provider, model, messages, temperature, api_key):
    url = PROVIDERS[provider]["base"] + "/chat/completions"
    body = json.dumps({"model": model, "messages": messages, "temperature": temperature}).encode()
    headers = {"Content-Type": "application/json"}
    if PROVIDERS[provider]["auth"]:
        headers["Authorization"] = f"Bearer {api_key}"
    req = urllib.request.Request(url, data=body, method="POST", headers=headers)
    t0 = time.time()
    with urllib.request.urlopen(req, timeout=120) as r:
        resp = json.loads(r.read().decode())
    latency = int((time.time() - t0) * 1000)
    content = resp["choices"][0]["message"]["content"]
    return {"content": content, "model": resp.get("model", model),
            "latency_ms": latency, "provider": provider}


# Provider health tracking: circuit breaker + exponential backoff (reconnect).
_PROVIDER_STATE: dict = {}
_STATE_LOCK = threading.Lock()
BACKOFF_CAP = 60.0  # seconds


def _st(provider):
    return _PROVIDER_STATE.setdefault(
        provider,
        {"consec_failures": 0, "backoff_until": 0.0, "last_success": 0.0, "last_error": None},
    )


def provider_ok(provider):
    with _STATE_LOCK:
        s = _st(provider)
        s["consec_failures"] = 0
        s["backoff_until"] = 0.0
        s["last_success"] = time.time()
        s["last_error"] = None


def provider_fail(provider, err):
    with _STATE_LOCK:
        s = _st(provider)
        s["consec_failures"] += 1
        s["backoff_until"] = time.time() + min(BACKOFF_CAP, 2 ** s["consec_failures"])
        s["last_error"] = str(err)[:200]


def provider_available(provider):
    with _STATE_LOCK:
        s = _st(provider)
        return time.time() >= s["backoff_until"]


def provider_status():
    with _STATE_LOCK:
        now = time.time()
        return {
            p: {
                "consec_failures": s["consec_failures"],
                "cooling_down": now < s["backoff_until"],
                "retry_in_s": max(0.0, round(s["backoff_until"] - now, 1)),
                "last_success": s["last_success"],
                "last_error": s["last_error"],
            }
            for p, s in _PROVIDER_STATE.items()
        }


def chat_with_reconnect(provider, model, messages, temperature, api_key):
    """Circuit-breaker + exponential backoff around call_chat."""
    if not provider_available(provider):
        s = provider_status().get(provider, {})
        return {"error": f"provider {provider} circuit-open (cooling down), retry in {s.get('retry_in_s', 0)}s"}
    try:
        result = call_chat(provider, model, messages, temperature, api_key)
        provider_ok(provider)
        return result
    except Exception as e:
        provider_fail(provider, e)
        raise


def _init_db():
    with _DB_LOCK:
        con = sqlite3.connect(REVIEWS_DB)
        try:
            con.execute(
                "CREATE TABLE IF NOT EXISTS reviews ("
                "id INTEGER PRIMARY KEY AUTOINCREMENT,"
                "model TEXT NOT NULL,"
                "author TEXT NOT NULL DEFAULT 'Аноним',"
                "rating INTEGER NOT NULL CHECK (rating BETWEEN 1 AND 5),"
                "text TEXT NOT NULL,"
                "ts TEXT NOT NULL DEFAULT (datetime('now')))"
            )
            con.execute("CREATE INDEX IF NOT EXISTS idx_reviews_model ON reviews(model)")
            con.commit()
        finally:
            con.close()


def get_reviews(model=None):
    _init_db()
    con = sqlite3.connect(REVIEWS_DB)
    try:
        con.row_factory = sqlite3.Row
        if model:
            rows = con.execute(
                "SELECT id, model, author, rating, text, ts FROM reviews WHERE model = ? ORDER BY id DESC",
                (model,),
            ).fetchall()
        else:
            rows = con.execute("SELECT id, model, author, rating, text, ts FROM reviews ORDER BY id DESC").fetchall()
        return [dict(r) for r in rows]
    finally:
        con.close()


def add_review(model, author, rating, text):
    _init_db()
    with _DB_LOCK:
        con = sqlite3.connect(REVIEWS_DB)
        try:
            cur = con.execute(
                "INSERT INTO reviews (model, author, rating, text) VALUES (?, ?, ?, ?)",
                (model, author, rating, text),
            )
            con.commit()
            rid = cur.lastrowid
            con.row_factory = sqlite3.Row
            row = con.execute("SELECT id, model, author, rating, text, ts FROM reviews WHERE id = ?", (rid,)).fetchone()
            return dict(row)
        finally:
            con.close()


def delete_review(rid):
    _init_db()
    with _DB_LOCK:
        con = sqlite3.connect(REVIEWS_DB)
        try:
            cur = con.execute("DELETE FROM reviews WHERE id = ?", (rid,))
            con.commit()
            return cur.rowcount > 0
        finally:
            con.close()


class H(BaseHTTPRequestHandler):
    def _cors(self):
        origin = self.headers.get("Origin")
        if origin in ALLOWED_ORIGINS:
            self.send_header("Access-Control-Allow-Origin", origin)
            self.send_header("Vary", "Origin")
        self.send_header("Access-Control-Allow-Methods", "GET,POST,DELETE,OPTIONS")
        self.send_header("Access-Control-Allow-Headers", "Content-Type")

    def _json(self, obj, code=200):
        data = json.dumps(obj, ensure_ascii=False).encode()
        self.send_response(code)
        self.send_header("Content-Type", "application/json; charset=utf-8")
        self.send_header("Content-Length", str(len(data)))
        self._cors()
        self.end_headers()
        self.wfile.write(data)

    def do_OPTIONS(self):
        self.send_response(204)
        self._cors()
        self.end_headers()

    def do_GET(self):
        if self.path == "/api/health":
            self._json({"ok": True, "providers": list(PROVIDERS.keys()), "port": PORT, "provider_status": provider_status()})
        elif self.path == "/api/providers":
            self._json(provider_status())
        elif self.path == "/api/models":
            self._json(MODELS)
        elif self.path == "/api/orchestra":
            try:
                with urllib.request.urlopen("http://127.0.0.1:8091/api/orchestra", timeout=8) as r:
                    data = r.read()
                self.send_response(200)
                self.send_header("Content-Type", "application/json; charset=utf-8")
                self.send_header("Content-Length", str(len(data)))
                self._cors()
                self.end_headers()
                self.wfile.write(data)
            except Exception as e:
                self._json({"error": f"orchestra dashboard unreachable: {str(e)[:200]}"}, 502)
        elif self.path in ("/api/skills", "/api/catalog"):
            fname = "skills.seed.json" if self.path == "/api/skills" else "models.seed.json"
            try:
                data = (SEED_DIR / fname).read_bytes()
                self.send_response(200)
                self.send_header("Content-Type", "application/json; charset=utf-8")
                self.send_header("Content-Length", str(len(data)))
                self._cors()
                self.end_headers()
                self.wfile.write(data)
            except Exception as e:
                self._json({"error": str(e)[:200]}, 500)
        elif self.path == "/api/openrouter":
            try:
                key = load_keys().get("openrouter_free")
                if not key:
                    self._json({"error": "no openrouter key"}, 400)
                    return
                req = urllib.request.Request("https://openrouter.ai/api/v1/models", headers={"Authorization": f"Bearer {key}"})
                with urllib.request.urlopen(req, timeout=30) as r:
                    data = r.read()
                self.send_response(200)
                self.send_header("Content-Type", "application/json; charset=utf-8")
                self.send_header("Content-Length", str(len(data)))
                self._cors()
                self.end_headers()
                self.wfile.write(data)
            except Exception as e:
                self._json({"error": f"openrouter unreachable: {str(e)[:200]}"}, 502)
        elif self.path.startswith("/api/reviews"):
            q = parse_qs(urlparse(self.path).query)
            model = (q.get("model") or [None])[0]
            self._json({"model": model, "reviews": get_reviews(model)})
        else:
            self._json({"error": "not found"}, 404)

    def do_POST(self):
        n = int(self.headers.get("Content-Length", 0))
        if n > 1_000_000:
            return self._json({"error": "payload too large"}, 413)
        try:
            payload = json.loads(self.rfile.read(n).decode())
        except Exception:
            return self._json({"error": "bad json"}, 400)
        if not isinstance(payload, dict):
            return self._json({"error": "payload must be an object"}, 400)

        if self.path == "/api/chat":
            provider = payload.get("provider", "ollama")
            if provider not in PROVIDERS:
                return self._json({"error": f"unknown provider {provider}"}, 400)
            model = payload.get("model")
            messages = payload.get("messages", [])
            temperature = payload.get("temperature", 0.7)
            api_key = load_keys().get(provider) if PROVIDERS[provider]["auth"] else None
            if PROVIDERS[provider]["auth"] and not api_key:
                return self._json({"error": f"no key for provider {provider}"}, 400)
            try:
                result = chat_with_reconnect(provider, model, messages, temperature, api_key)
                if "error" in result:
                    self._json(result, 503)
                else:
                    self._json(result)
            except urllib.error.HTTPError as e:
                self._json({"error": f"provider {e.code}: {e.read().decode()[:300]}"}, 502)
            except Exception as e:
                self._json({"error": str(e)[:300]}, 500)

        elif self.path == "/api/reviews":
            model = (payload.get("model") or "").strip()
            author = (payload.get("author") or "").strip()[:80] or "Аноним"
            text = (payload.get("text") or "").strip()[:2000]
            try:
                rating = int(payload.get("rating", 0))
            except (TypeError, ValueError):
                rating = 0
            if not model:
                return self._json({"error": "model is required"}, 400)
            if not text:
                return self._json({"error": "text is required"}, 400)
            if not (1 <= rating <= 5):
                return self._json({"error": "rating must be 1..5"}, 400)
            try:
                self._json(add_review(model, author, rating, text), 201)
            except Exception as e:
                self._json({"error": str(e)[:300]}, 500)

        else:
            self._json({"error": "not found"}, 404)

    def do_DELETE(self):
        parts = self.path.split("/")
        if len(parts) == 4 and parts[1] == "api" and parts[2] == "reviews":
            try:
                rid = int(parts[3])
            except ValueError:
                return self._json({"error": "bad id"}, 400)
            try:
                if delete_review(rid):
                    self._json({"ok": True, "deleted": rid})
                else:
                    self._json({"error": "not found"}, 404)
            except Exception as e:
                self._json({"error": str(e)[:300]}, 500)
        else:
            self._json({"error": "not found"}, 404)

    def log_message(self, *a):
        pass


if __name__ == "__main__":
    print(f"playground_proxy on http://127.0.0.1:{PORT}", flush=True)
    ThreadingHTTPServer(("127.0.0.1", PORT), H).serve_forever()
