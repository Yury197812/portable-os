"""Live FAN_OUT demo: WORKER_A executes via runtime :8891, WORKER_B honest skip."""
import json
import sys
import urllib.request
from pathlib import Path

sys.path.insert(0, str(Path(r"D:\4\OUT\MIMO")))
import multiworker as mw  # noqa: E402


def exec_a(worker_id, task):
    req = urllib.request.Request(
        "http://127.0.0.1:8891/api/runs",
        data=json.dumps({"model": "qwen2.5:14b", "prompt": "Reply with exactly: OK"}).encode(),
        headers={"Content-Type": "application/json"},
    )
    r = json.loads(urllib.request.urlopen(req, timeout=120).read())
    return {
        "output": r.get("output"),
        "latency_ms": r.get("latency_ms"),
        "failure_rate": 0.0,
        "output_refs": [task["task_id"] + "-a"],
        "provenance": ["runtime-live"],
        "fencing_token": 1,
    }


report = mw.fan_out({"task_id": "fanout-live-1", "mode": "FAN_OUT"}, ["MIMO_DEEPSEEK", "MIMO_MINIMAX"], exec_a)
print("PER_WORKER:", json.dumps(report["per_worker"], ensure_ascii=False))
print("MERGED verdict:", report["merged"]["verdict"], "accepted:", len(report["merged"]["accepted"]))

res_a = report["per_worker"]["MIMO_DEEPSEEK"].get("result", {})
bc = mw.battlecheck({"MIMO_DEEPSEEK": {"output": res_a.get("output"), "latency_ms": res_a.get("latency_ms")}})
print("BATTLECHECK:", json.dumps(bc, ensure_ascii=False))

print("WORKER_STATUS:", json.dumps(mw.worker_status(), ensure_ascii=False))
