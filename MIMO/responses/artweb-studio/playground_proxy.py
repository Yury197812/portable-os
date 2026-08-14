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
import time
import urllib.error
import urllib.request
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path

KEYS_PATH = Path(r"D:\4\04_utilities\api_keys.json")
SEED_DIR = Path(__file__).parent
PORT = 8890

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


class H(BaseHTTPRequestHandler):
    def _cors(self):
        self.send_header("Access-Control-Allow-Origin", "*")
        self.send_header("Access-Control-Allow-Methods", "GET,POST,OPTIONS")
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
            self._json({"ok": True, "providers": list(PROVIDERS.keys()), "port": PORT})
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
        else:
            self._json({"error": "not found"}, 404)

    def do_POST(self):
        if self.path != "/api/chat":
            return self._json({"error": "not found"}, 404)
        n = int(self.headers.get("Content-Length", 0))
        try:
            payload = json.loads(self.rfile.read(n).decode())
        except Exception:
            return self._json({"error": "bad json"}, 400)
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
            self._json(call_chat(provider, model, messages, temperature, api_key))
        except urllib.error.HTTPError as e:
            self._json({"error": f"provider {e.code}: {e.read().decode()[:300]}"}, 502)
        except Exception as e:
            self._json({"error": str(e)[:300]}, 500)

    def log_message(self, *a):
        pass


if __name__ == "__main__":
    print(f"playground_proxy on http://127.0.0.1:{PORT}", flush=True)
    ThreadingHTTPServer(("127.0.0.1", PORT), H).serve_forever()
