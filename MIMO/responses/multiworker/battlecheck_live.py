#!/usr/bin/env python3
"""battlecheck_live.py — честный BATTLECHECK WORKER_A vs WORKER_B.

A = real measured numbers (capability_measure over qwen2.5:14b).
B = read from WORKER_B GitHub namespace (status/HEARTBEAT.json). If B has no
    calibrated capabilities, verdict is INCOMPLETE (B registered, not calibrated)
    — never fabricate B's numbers.

Stdlib-only.
"""
import json
import sys
import urllib.request
from pathlib import Path

sys.path.insert(0, str(Path(r"D:\4\OUT\MIMO")))
import multiworker as mw  # noqa: E402
import capability_measure as cm  # noqa: E402

B_STATUS_URL = "https://raw.githubusercontent.com/Yury197812/portable-os/master/MIMO/workers/MIMO_MINIMAX/status/HEARTBEAT.json"
B_REGISTERED_URL = "https://raw.githubusercontent.com/Yury197812/portable-os/master/MIMO/workers/MIMO_MINIMAX/status/REGISTERED.json"


def fetch(url):
    with urllib.request.urlopen(url, timeout=20) as r:
        return json.loads(r.read().decode())


def main() -> int:
    # --- WORKER_A: real measurement (or load persisted) ---
    a_caps = {}
    try:
        # try persisted first; if empty, run a fresh measurement
        if mw.load_capabilities("MIMO_DEEPSEEK").get("ok"):
            a_caps = mw.capability_status("MIMO_DEEPSEEK")["calibrated"]
        else:
            cm.measure("MIMO_DEEPSEEK", "qwen2.5:14b", rounds=3)
            a_caps = mw.capability_status("MIMO_DEEPSEEK")["calibrated"]
    except Exception as e:
        print("A measurement failed:", e)
        return 1

    # --- WORKER_B: read its namespace (honest — no fabrication) ---
    b_state = {}
    try:
        b_heartbeat = fetch(B_STATUS_URL)
        b_registered = fetch(B_REGISTERED_URL)
        b_verified = b_heartbeat.get("capabilities_verified", [])
        b_state = {
            "registered": True,
            "status": b_heartbeat.get("status"),
            "capabilities_verified": b_verified,
            "calibrated": bool(b_verified),  # empty list = NOT calibrated
        }
    except Exception as e:
        b_state = {"registered": False, "error": str(e)[:120]}

    # --- build battlecheck inputs ---
    # A: map dimension verdicts to observed numbers
    a_result = {
        "latency_ms": a_caps["latency_ms"]["mean"],
        "failure_rate": a_caps["failure_rate"]["mean"],
        "output": True,
    }
    b_result = None
    if b_state.get("calibrated"):
        # B actually calibrated — would read its numbers here; not the case now
        b_result = b_state.get("calibration_numbers")

    results_by_worker = {"MIMO_DEEPSEEK": a_result}
    if b_result is not None:
        results_by_worker["MIMO_MINIMAX"] = b_result

    verdict = mw.battlecheck(results_by_worker)

    out = {
        "worker_a": {
            "worker_id": "MIMO_DEEPSEEK",
            "latency_ms": a_caps["latency_ms"],
            "failure_rate": a_caps["failure_rate"],
            "code": a_caps["code"]["verdict"],
            "quality": a_caps["quality"]["verdict"],
        },
        "worker_b": b_state,
        "battlecheck": verdict,
    }
    print(json.dumps(out, ensure_ascii=False, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
