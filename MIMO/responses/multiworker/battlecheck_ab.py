#!/usr/bin/env python3
"""battlecheck_ab.py — честный BATTLECHECK WORKER_A vs WORKER_B на реальных цифрах.

A = capability_measure (qwen2.5:14b via Ollama/runtime).
B = WORKER_B CALIBRATION.json (MiniMax-M3 via api.minimax.io).

Оба набора — реальные замеры, ничего не выдумано."""
import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(r"D:\4\OUT\MIMO")))
import multiworker as mw  # noqa: E402

B_CAL = Path(r"D:\4\OUT\MIMO_MINIMAX\results\CALIBRATION.json")


def main() -> int:
    # A: persisted capability registry (real measured qwen2.5:14b)
    mw.load_capabilities("MIMO_DEEPSEEK")
    a_status = mw.capability_status("MIMO_DEEPSEEK")["calibrated"]

    # B: CALIBRATION.json (real measured MiniMax-M3)
    b_cal = json.loads(B_CAL.read_text(encoding="utf-8")) if B_CAL.exists() else None

    a_result = {
        "latency_ms": a_status["latency_ms"]["mean"],
        "failure_rate": a_status["failure_rate"]["mean"],
        "output": True,
    }
    b_result = None
    if b_cal and b_cal["results"].get("latency_ms", {}).get("ok"):
        b_result = {
            "latency_ms": b_cal["results"]["latency_ms"]["mean"],
            "failure_rate": b_cal["results"]["failure_rate"].get("failure_rate"),
            "output": True,
        }

    results = {"MIMO_DEEPSEEK": a_result}
    if b_result is not None:
        results["MIMO_MINIMAX"] = b_result

    verdict = mw.battlecheck(results)

    print(json.dumps({
        "worker_a": {
            "model": "qwen2.5:14b (Ollama)",
            "latency_ms": a_status["latency_ms"],
            "failure_rate": a_status["failure_rate"],
            "code": a_status["code"]["verdict"],
            "quality": a_status["quality"]["verdict"],
            "long_context": a_status["long_context"]["verdict"],
        },
        "worker_b": {
            "model": "MiniMax-M3 (api.minimax.io)",
            "results": b_cal["results"] if b_cal else None,
        },
        "battlecheck": verdict,
    }, ensure_ascii=False, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
