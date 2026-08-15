#!/usr/bin/env python3
"""calibrate_deepseek.py — fresh calibration of WORKER_A on the ACTUAL
deepseek-v4-pro backend (api.deepseek.com), per OCULUS v1.3.0.

Probes: quality, code/debug, long_context, latency, failure_rate, tool_use.
This is DeepSeek, NOT Qwen — Qwen stays a separate candidate configuration.

Stdlib-only.
"""
from __future__ import annotations

import json
import os
import time
import urllib.request

DEEPSEEK_URL = "https://api.deepseek.com/v1/chat/completions"
MODEL = "deepseek-v4-pro"
ROUNDS = 3


def chat_once(messages: list, tools=None) -> dict:
    key = os.environ.get("DEEPSEEK_API_KEY")
    if not key:
        raise RuntimeError("DEEPSEEK_API_KEY not set")
    body = {"model": MODEL, "messages": messages}
    if tools is not None:
        body["tools"] = tools
    req = urllib.request.Request(DEEPSEEK_URL, data=json.dumps(body).encode(), method="POST",
                                 headers={"Content-Type": "application/json", "Authorization": "Bearer " + key})
    t0 = time.time()
    with urllib.request.urlopen(req, timeout=180) as r:
        resp = json.loads(r.read().decode())
    latency = int((time.time() - t0) * 1000)
    msg = resp["choices"][0]["message"]
    return {"content": msg.get("content") or "", "tool_calls": msg.get("tool_calls"), "latency_ms": latency}


def _u(text):
    return {"role": "user", "content": text}


def probe_latency():
    values = []
    for _ in range(ROUNDS):
        values.append(chat_once([_u("Say OK")])["latency_ms"])
    return {"ok": True, "values": values, "mean": round(sum(values) / len(values), 1), "min": min(values), "max": max(values)}


def probe_failure_rate():
    failures = 0
    for _ in range(ROUNDS):
        try:
            chat_once([_u("ping")])
        except Exception:
            failures += 1
    return {"ok": failures == 0, "failures": failures, "total": ROUNDS, "failure_rate": failures / ROUNDS}


def probe_quality():
    ok = 0
    for _ in range(ROUNDS):
        try:
            r = chat_once([_u("What is 12 * 13? Reply with only the number.")])
            if "156" in r["content"]:
                ok += 1
        except Exception:
            continue
    return {"ok": ok == ROUNDS, "passed": ok, "total": ROUNDS}


def probe_code_debug():
    ok = 0
    for _ in range(ROUNDS):
        try:
            r = chat_once([_u("Output ONLY a Python function `def add(a,b): return a+b` with no explanation.")])
            code = r["content"]
            if "```" in code:
                code = code.split("```")[1].replace("python", "", 1)
            compile(code, "<model>", "exec")
            ok += 1
        except Exception:
            continue
    return {"ok": ok == ROUNDS, "passed": ok, "total": ROUNDS}


def probe_long_context():
    ok = 0
    fact = "The capital of France is Paris."
    prompt = "filler line. " * 400 + f"Read the last sentence only: {fact} Now answer: What is the capital of France? Reply with one word."
    for _ in range(ROUNDS):
        try:
            r = chat_once([_u(prompt)])
            if "Paris" in r["content"]:
                ok += 1
        except Exception:
            continue
    return {"ok": ok == ROUNDS, "passed": ok, "total": ROUNDS}


def probe_tool_use():
    """Real tool_use execution: ask the model to call a tool, check tool_calls
    in the response (readback). DeepSeek v4-pro may or may not support
    native tool_calls — report honestly."""
    tools = [{
        "type": "function",
        "function": {"name": "get_weather", "description": "Get weather", "parameters": {"type": "object", "properties": {"city": {"type": "string"}}, "required": ["city"]}},
    }]
    ok = 0
    for _ in range(ROUNDS):
        try:
            r = chat_once([_u("What is the weather in Paris? Use the get_weather tool.")], tools=tools)
            if r.get("tool_calls"):
                ok += 1
        except Exception:
            continue
    return {"ok": ok == ROUNDS, "passed": ok, "total": ROUNDS, "supported": ok > 0}


PROBES = [
    ("latency", probe_latency),
    ("failure_rate", probe_failure_rate),
    ("quality", probe_quality),
    ("code_debug", probe_code_debug),
    ("long_context", probe_long_context),
    ("tool_use", probe_tool_use),
]


def main() -> int:
    report = {
        "worker_id": "MIMO_DEEPSEEK",
        "model": MODEL,
        "backend": "api.deepseek.com (real DeepSeek, NOT Qwen proxy)",
        "rounds": ROUNDS,
        "timestamp": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()),
        "results": {},
    }
    verified = []
    for name, fn in PROBES:
        try:
            report["results"][name] = fn()
            if report["results"][name].get("ok"):
                verified.append(name)
        except Exception as e:
            report["results"][name] = {"ok": False, "error": str(e)[:200]}
    report["verified"] = verified
    print(json.dumps(report, ensure_ascii=False, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
