#!/usr/bin/env python3
"""calibrate_worker_b.py — WORKER_B (MiniMax) capability calibration.

Runs the same empirical battle probes as WORKER_A, but against the MiniMax
API. Writes the result to WORKER_B's own namespace:
  status/HEARTBEAT.json  -> capabilities_verified populated
  results/CALIBRATION.json -> full per-dimension report

Honesty:
- If the MiniMax key is invalid (HTTP 401 / base_resp 2049), calibration is
  BLOCKED and nothing is fabricated: capabilities_verified stays [].
- The key comes ONLY from env MINIMAX_API_KEY, never hard-coded.

Run from WORKER_B's work root (D:\4\OUT\MIMO_MINIMAX) by WORKER_B itself.
Stdlib-only.
"""
from __future__ import annotations

import json
import os
import sys
import time
import urllib.request
from pathlib import Path

# MiniMax endpoint (native MiniMax API, not OpenAI-compatible).
MINIMAX_URL = "https://api.minimaxi.com/v1/text/chatcompletion_v2"
MINIMAX_MODEL = "MiniMax-Text-01"

WORKER_B_ROOT = Path(r"D:\4\OUT\MIMO_MINIMAX")
STATUS_PATH = WORKER_B_ROOT / "status" / "HEARTBEAT.json"
RESULTS_PATH = WORKER_B_ROOT / "results" / "CALIBRATION.json"

# probe dimensions matching WORKER_A (latency, failure_rate, code, quality,
# long_context, tool_use). cost stays NOT_RUN without a pricing source.
ROUNDS = 3


def chat_once(messages: list) -> dict:
    key = os.environ.get("MINIMAX_API_KEY")
    if not key:
        raise RuntimeError("MINIMAX_API_KEY not set")
    body = json.dumps({"model": MINIMAX_MODEL, "messages": messages}).encode()
    req = urllib.request.Request(MINIMAX_URL, data=body, method="POST",
                                 headers={"Content-Type": "application/json", "Authorization": f"Bearer {key}"})
    t0 = time.time()
    with urllib.request.urlopen(req, timeout=60) as r:
        resp = json.loads(r.read().decode())
    latency = int((time.time() - t0) * 1000)
    if resp.get("base_resp", {}).get("status_code", 0) != 0:
        raise RuntimeError(f"MiniMax API error {resp['base_resp'].get('status_code')}: {resp['base_resp'].get('status_msg')}")
    content = "".join(ch.get("text", "") for ch in resp.get("reply", "").split("\n")) if isinstance(resp.get("reply"), str) else resp.get("reply", "")
    # MiniMax returns reply as a plain string for MiniMax-Text
    if isinstance(resp.get("reply"), str):
        content = resp["reply"]
    return {"content": content, "latency_ms": latency}


def _user(text):
    return {"sender_type": "USER", "text": text}


def probe_latency(rounds=ROUNDS):
    values = []
    for _ in range(rounds):
        values.append(chat_once([_user("Say OK")])["latency_ms"])
    return {"ok": True, "values": values, "mean": sum(values) / len(values), "min": min(values), "max": max(values)}


def probe_failure_rate(rounds=ROUNDS):
    failures = 0
    for _ in range(rounds):
        try:
            chat_once([_user("ping")])
        except Exception:
            failures += 1
    return {"ok": failures == 0, "failures": failures, "total": rounds, "failure_rate": failures / rounds}


def probe_quality(rounds=ROUNDS):
    ok = 0
    for _ in range(rounds):
        try:
            r = chat_once([_user("What is 12 * 13? Reply with only the number.")])
            if "156" in r["content"]:
                ok += 1
        except Exception:
            continue
    return {"ok": ok == rounds, "passed": ok, "total": rounds}


def probe_long_context(rounds=ROUNDS):
    ok = 0
    secret = "ZEBRA-4271"
    prompt = "filler line. " * 400 + f"The secret code is {secret}. Reply with only that code."
    for _ in range(rounds):
        try:
            r = chat_once([_user(prompt)])
            if secret in r["content"]:
                ok += 1
        except Exception:
            continue
    return {"ok": ok == rounds, "passed": ok, "total": rounds}


def probe_code(rounds=ROUNDS):
    ok = 0
    for _ in range(rounds):
        try:
            r = chat_once([_user("Output ONLY a Python function `def add(a,b): return a+b` with no explanation.")])
            code = r["content"]
            if "```" in code:
                code = code.split("```")[1].replace("python", "", 1)
            compile(code, "<model>", "exec")
            ok += 1
        except Exception:
            continue
    return {"ok": ok == rounds, "passed": ok, "total": rounds}


PROBES = {
    "latency_ms": probe_latency,
    "failure_rate": probe_failure_rate,
    "code": probe_code,
    "quality": probe_quality,
    "long_context": probe_long_context,
}


def calibrate():
    report = {"worker_id": "MIMO_MINIMAX", "model": MINIMAX_MODEL, "rounds": ROUNDS,
              "timestamp": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()), "results": {}, "verified": []}

    for dim, fn in PROBES.items():
        try:
            probe = fn()
            report["results"][dim] = probe
            if probe.get("ok"):
                report["verified"].append(dim)
        except Exception as e:
            report["results"][dim] = {"ok": False, "error": str(e)[:200]}

    # Persist to WORKER_B's own namespace (only if not fully blocked)
    RESULTS_PATH.parent.mkdir(parents=True, exist_ok=True)
    RESULTS_PATH.write_text(json.dumps(report, ensure_ascii=False, indent=2), encoding="utf-8")

    # update HEARTBEAT.json capabilities_verified (only if heartbeat exists)
    if STATUS_PATH.exists():
        hb = json.loads(STATUS_PATH.read_text(encoding="utf-8-sig"))  # PowerShell writes BOM
        hb["capabilities_verified"] = report["verified"]
        hb["timestamp"] = report["timestamp"]
        STATUS_PATH.write_text(json.dumps(hb, ensure_ascii=False, indent=2), encoding="utf-8")

    report["blocked"] = len(report["verified"]) == 0
    return report


def main() -> int:
    report = calibrate()
    print(json.dumps(report, ensure_ascii=False, indent=2))
    return 0 if not report["blocked"] else 2


if __name__ == "__main__":
    raise SystemExit(main())
