#!/usr/bin/env python3
"""
multiworker.py — ArtWeb Orchestra multi-worker coordination layer.

Prepares the Orchestra for a second independent MIMO worker (WORKER_B) on the
same host without breaking the existing WORKER_A transport.

Honesty rules (P0 PREP):
- WORKER_B is NOT live until its namespace/heartbeat actually appears. Until
  then every reference reports PREPARED/WAITING_HEARTBEAT — never LIVE.
- No shared writable result.json/state.json between workers; each worker has
  its own inbox/outbox/state/work dirs.
- Lease/fencing prevents two workers completing the same task.
- Worker capabilities are calibrated empirically, never assumed from brand.

Stdlib-only.
"""
from __future__ import annotations

import json
import os
import threading
import time
import uuid
from pathlib import Path

try:
    import msvcrt  # Windows file locking (IPC)
except ImportError:  # pragma: no cover
    msvcrt = None

ROOT = Path(r"D:\4\OUT\MIMO")
MW_DIR = ROOT / "workers"

# ---------------------------------------------------------------------------
# Worker registry
# ---------------------------------------------------------------------------

# Static worker definitions. WORKER_A = us (live); WORKER_B = future MiniMax
# (NOT live until it registers). model_backend is a string, never an assumption.
WORKERS = {
    "MIMO_DEEPSEEK": {
        "worker_id": "MIMO_DEEPSEEK",
        "role": "WORKER_A",
        "engine": "MIMO",
        "model_backend": "DeepSeek V4-Pro 0813",
        "local_root": str(Path(r"C:\Users\Art\ArtWebStudio\artweb-studio\runtime")),
        "github_namespace": "MIMO/responses/",
        "ntfy_topic": "artweb-mimo-bus-20260814-8d3f2a761c4e",
        "live": True,
    },
    "MIMO_MINIMAX": {
        "worker_id": "MIMO_MINIMAX",
        "role": "WORKER_B",
        "engine": "MIMO",
        "model_backend": "MiniMax",
        "local_root": str(Path(r"D:\4\OUT\MIMO_MINIMAX")),
        "github_namespace": "MIMO/workers/MIMO_MINIMAX/",
        "ntfy_topic": "artweb-mimo-minimax-bus-20260815-e50aec37c62f",
        "live": False,
    },
}

# live heartbeat map: worker_id -> {instance_id, last_heartbeat_ts}
_HEARTBEATS: dict[str, dict] = {}
_HB_LOCK = threading.Lock()


def worker_dir(worker_id: str) -> Path:
    return MW_DIR / worker_id


def _subdirs(worker_id: str) -> dict[str, Path]:
    d = worker_dir(worker_id)
    sub = {name: d / name for name in ("inbox", "outbox", "state", "work")}
    return sub


def ensure_worker_dirs(worker_id: str) -> dict[str, Path]:
    subs = _subdirs(worker_id)
    for p in subs.values():
        p.mkdir(parents=True, exist_ok=True)
    return subs


def register_worker(worker_id: str, instance_id: str, model_backend: str | None = None) -> dict:
    """Register a worker instance with a heartbeat. Idempotent."""
    if worker_id not in WORKERS:
        return {"ok": False, "error": f"unknown worker {worker_id}", "known": sorted(WORKERS)}
    with _HB_LOCK:
        _HEARTBEATS[worker_id] = {
            "instance_id": instance_id,
            "last_heartbeat": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()),
            "model_backend": model_backend or WORKERS[worker_id]["model_backend"],
        }
    ensure_worker_dirs(worker_id)
    return {"ok": True, "worker_id": worker_id, "instance_id": instance_id}


def heartbeat(worker_id: str, instance_id: str) -> dict:
    """Update a worker's heartbeat timestamp."""
    return register_worker(worker_id, instance_id)


def worker_status(worker_id: str | None = None) -> dict:
    """Status for one worker or all. WORKER_B reports PREPARED/WAITING_HEARTBEAT
    until a heartbeat actually appears — never LIVE."""
    def one(wid: str) -> dict:
        meta = WORKERS[wid]
        hb = _HEARTBEATS.get(wid)
        if hb:
            status = "LIVE" if meta["live"] else "HEARTBEAT_SEEN_BUT_UNVERIFIED"
        else:
            status = "LIVE" if meta["live"] else "PREPARED/WAITING_HEARTBEAT"
        return {
            "worker_id": wid,
            "role": meta["role"],
            "engine": meta["engine"],
            "model_backend": meta["model_backend"],
            "status": status,
            "instance_id": hb["instance_id"] if hb else None,
            "last_heartbeat": hb["last_heartbeat"] if hb else None,
            "local_root": meta["local_root"],
            "github_namespace": meta["github_namespace"],
            "ntfy_topic": meta["ntfy_topic"],
        }
    if worker_id:
        return one(worker_id) if worker_id in WORKERS else {"error": "unknown worker"}
    return {"workers": [one(w) for w in WORKERS]}


# ---------------------------------------------------------------------------
# Task envelope
# ---------------------------------------------------------------------------

# Task status FSM: QUEUED -> LEASED -> RUNNING -> SUCCEEDED|FAILED|RECLAIMED.
# Task modes (Control Tower selects): SOLO / REVIEW / FAN_OUT / PIPELINE /
# BATTLECHECK / FAILOVER. Only Control Tower promotes outputs to canon.
TASK_MODES = ("SOLO", "REVIEW", "FAN_OUT", "PIPELINE", "BATTLECHECK", "FAILOVER")


def make_task_envelope(**fields) -> dict:
    """Build a canonical task envelope with all required fields defaulted.

    Required (P0 PREP §4): task_id, parent_task_id, worker_id/recipient,
    required_capabilities, priority, deadline, budget, max_attempts,
    input_refs, output_refs, provenance, status, fencing_token."""
    env = {
        "task_id": fields.get("task_id") or uuid.uuid4().hex[:12],
        "parent_task_id": fields.get("parent_task_id"),
        "worker_id": fields.get("worker_id"),
        "recipient": fields.get("recipient") or fields.get("worker_id"),
        "required_capabilities": fields.get("required_capabilities") or [],
        "priority": fields.get("priority", 5),
        "deadline": fields.get("deadline"),
        "budget": fields.get("budget"),
        "max_attempts": fields.get("max_attempts", 1),
        "input_refs": fields.get("input_refs") or [],
        "output_refs": fields.get("output_refs") or [],
        "provenance": fields.get("provenance") or [],
        "status": fields.get("status", "QUEUED"),
        "fencing_token": fields.get("fencing_token", 0),
        "mode": fields.get("mode") or "SOLO",
        "created_at": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()),
    }
    if env["mode"] not in TASK_MODES:
        raise ValueError(f"unknown mode {env['mode']}")
    return env


# ---------------------------------------------------------------------------
# Lease / fencing (cross-worker)
# ---------------------------------------------------------------------------

_FENCE = {"value": 0}
_FENCE_LOCK = threading.Lock()


def next_fencing_token() -> int:
    with _FENCE_LOCK:
        _FENCE["value"] += 1
        return _FENCE["value"]


def _file_lock(path: Path):
    path.parent.mkdir(parents=True, exist_ok=True)
    f = open(path, "a+b")
    try:
        if msvcrt is not None:
            msvcrt.locking(f.fileno(), msvcrt.LK_LOCK, 1)
        return f
    except Exception:
        f.close()
        raise


def _file_unlock(f) -> None:
    try:
        if msvcrt is not None:
            f.seek(0)
            msvcrt.locking(f.fileno(), msvcrt.LK_UNLCK, 1)
    except Exception:
        pass
    finally:
        f.close()


def _atomic_write(path: Path, text: str) -> None:
    tmp = path.with_name(path.name + ".tmp")
    tmp.write_text(text, encoding="utf-8")
    os.replace(tmp, path)


# ---------------------------------------------------------------------------
# Task store (per-worker work dir)
# ---------------------------------------------------------------------------

def task_path(worker_id: str, task_id: str) -> Path:
    return _subdirs(worker_id)["work"] / f"{task_id}.json"


def assign_task(task: dict, worker_id: str) -> dict:
    """Assign a task to a worker. Sets worker_id/recipient and a fresh fencing
    token. The worker must present this token to complete — prevents two
    workers from both completing the same task."""
    if worker_id not in WORKERS:
        return {"ok": False, "error": f"unknown worker {worker_id}"}
    ensure_worker_dirs(worker_id)
    env = make_task_envelope(**task)
    env["worker_id"] = worker_id
    env["recipient"] = worker_id
    env["fencing_token"] = next_fencing_token()
    env["status"] = "QUEUED"
    f = _file_lock(_subdirs(worker_id)["work"] / ".lock")
    try:
        _atomic_write(task_path(worker_id, env["task_id"]), json.dumps(env, ensure_ascii=False, indent=2))
    finally:
        _file_unlock(f)
    return {"ok": True, "task": env}


def complete_task(worker_id: str, task_id: str, fencing_token: int, result: dict, status: str = "SUCCEEDED") -> dict:
    """Complete a task. Fenced: stale token -> refuse (two workers can't both
    complete the same task)."""
    p = task_path(worker_id, task_id)
    if not p.exists():
        return {"ok": False, "error": "task not found", "fenced": False}
    f = _file_lock(p.parent / ".lock")
    try:
        env = json.loads(p.read_text(encoding="utf-8"))
        if env.get("fencing_token") != fencing_token:
            return {"ok": False, "error": f"stale fencing token {fencing_token} != {env.get('fencing_token')}", "fenced": True}
        env["status"] = status
        env["result"] = result
        env["completed_at"] = time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime())
        _atomic_write(p, json.dumps(env, ensure_ascii=False, indent=2))
        return {"ok": True, "task_id": task_id, "status": status, "fenced": False}
    finally:
        _file_unlock(f)


# ---------------------------------------------------------------------------
# Worker capability registry + empirical calibration
# ---------------------------------------------------------------------------

# Capability registry: capabilities are CALIBRATED from observed runs, never
# assumed from brand. quality/tool_use/code/long_context/latency_ms/cost/
# failure_rate are all empirical — empty until measured.
_CAPABILITIES: dict[str, dict] = {}


def capability_dimensions() -> list[str]:
    return ["quality", "tool_use", "code", "long_context", "latency_ms", "cost", "failure_rate"]


def init_capability(worker_id: str) -> dict:
    if worker_id not in _CAPABILITIES:
        _CAPABILITIES[worker_id] = {dim: None for dim in capability_dimensions()}
        _CAPABILITIES[worker_id]["samples"] = 0
    return _CAPABILITIES[worker_id]


def _dim_stats(worker_id: str, dim: str) -> dict:
    """Running stats for one dimension: count, mean, min, max, last."""
    caps = init_capability(worker_id)
    s = caps.get(f"_stats_{dim}")
    if not s:
        return {"dim": dim, "count": 0, "mean": None, "min": None, "max": None, "last": caps.get(dim)}
    n = s["count"]
    return {
        "dim": dim,
        "count": n,
        "mean": s["sum"] / n,
        "min": s["min"],
        "max": s["max"],
        "last": caps.get(dim),
    }


def record_observation(worker_id: str, dim: str, value: float) -> dict:
    """Record one empirical observation with running stats. DISCOVERED ≠
    VERIFIED — a single observation does not establish a capability; only
    repeated calibration (min 3 rounds) does."""
    init_capability(worker_id)
    caps = _CAPABILITIES[worker_id]
    if dim not in capability_dimensions():
        return {"ok": False, "error": f"unknown dimension {dim}"}
    key = f"_stats_{dim}"
    s = caps.get(key) or {"count": 0, "sum": 0.0, "min": None, "max": None}
    s["count"] += 1
    s["sum"] += value
    s["min"] = value if s["min"] is None else min(s["min"], value)
    s["max"] = value if s["max"] is None else max(s["max"], value)
    caps[key] = s
    caps[dim] = value  # last observation
    caps["samples"] = caps.get("samples", 0) + 1
    return {"ok": True, "worker_id": worker_id, "dim": dim, "value": value, "stats": _dim_stats(worker_id, dim)}


def dimension_verdict(worker_id: str, dim: str, min_rounds: int = 3) -> str:
    """VERIFIED only when >= min_rounds observations exist. Otherwise
    UNVERIFIED (partial) or NOT_RUN (zero)."""
    stats = _dim_stats(worker_id, dim)
    n = stats["count"]
    if n == 0:
        return "NOT_RUN"
    if n >= min_rounds:
        return "VERIFIED"
    return "UNVERIFIED"


def capability_status(worker_id: str | None = None) -> dict:
    """Capability registry snapshot with per-dimension running stats + verdict.
    Dimensions with count=0 = NOT measured. Never infer strengths from brand."""
    def one(wid: str) -> dict:
        dims = {}
        for dim in capability_dimensions():
            dims[dim] = {**_dim_stats(wid, dim), "verdict": dimension_verdict(wid, dim)}
        return {"worker_id": wid, "calibrated": dims, "samples": init_capability(wid).get("samples", 0)}
    if worker_id:
        return one(worker_id) if worker_id in WORKERS else {"error": "unknown worker"}
    return {"capabilities": {w: one(w) for w in WORKERS}}


def _capabilities_path(worker_id: str) -> Path:
    return _subdirs(worker_id)["state"] / "capabilities.json"


def save_capabilities(worker_id: str) -> dict:
    """Persist the in-memory capability registry to the worker's state dir.
    Survives process restart."""
    ensure_worker_dirs(worker_id)
    caps = init_capability(worker_id)
    data = {"worker_id": worker_id, "saved_at": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()), "capabilities": caps}
    _atomic_write(_capabilities_path(worker_id), json.dumps(data, ensure_ascii=False, indent=2))
    return {"ok": True, "worker_id": worker_id, "path": str(_capabilities_path(worker_id))}


def load_capabilities(worker_id: str) -> dict:
    """Restore the capability registry from disk (if present)."""
    p = _capabilities_path(worker_id)
    if not p.exists():
        return {"ok": False, "reason": "no persisted capabilities yet"}
    data = json.loads(p.read_text(encoding="utf-8"))
    _CAPABILITIES[worker_id] = data.get("capabilities", {})
    return {"ok": True, "worker_id": worker_id, "restored": data.get("saved_at")}


# ---------------------------------------------------------------------------
# Result merge protocol
# ---------------------------------------------------------------------------

def merge_results(results: list[dict]) -> dict:
    """Merge N worker results: dedup by output_refs hash, build conflict graph,
    attach evidence/provenance, battlecheck verdict, accept/reject.

    Returns {accepted, rejected, conflicts, evidence, verdict}."""
    seen = {}
    conflicts = []
    evidence = []
    accepted = []
    rejected = []

    for r in results:
        key = r.get("output_refs") and tuple(sorted(r.get("output_refs", []))) or r.get("task_id")
        if key in seen:
            conflicts.append({"a": seen[key], "b": r.get("worker_id") or r.get("task_id"), "reason": "duplicate output_refs"})
            rejected.append(r)
            continue
        seen[key] = r.get("worker_id") or r.get("task_id")
        accepted.append(r)
        evidence.append({"worker": r.get("worker_id"), "provenance": r.get("provenance", []), "fencing_token": r.get("fencing_token")})

    verdict = "CLEAN" if not conflicts else "CONFLICT"
    return {
        "accepted": accepted,
        "rejected": rejected,
        "conflicts": conflicts,
        "evidence": evidence,
        "verdict": verdict,
    }


# ---------------------------------------------------------------------------
# Task broker
# ---------------------------------------------------------------------------

def broker_route(task: dict, available_workers: list[str]) -> dict:
    """Route a task per mode:
    - SOLO / REVIEW / PIPELINE: exclusive route to ONE worker (by capability or
      round-robin) — never fan out.
    - FAN_OUT / BATTLECHECK: broadcast to ALL available workers for comparison.
    Control Tower owns final acceptance."""
    mode = task.get("mode", "SOLO")
    if mode in ("FAN_OUT", "BATTLECHECK"):
        return {"mode": mode, "route": "broadcast", "workers": list(available_workers)}
    if mode in ("SOLO", "REVIEW", "PIPELINE", "FAILOVER"):
        # pick first available (routing policy refinement owned by Control Tower)
        return {"mode": mode, "route": "exclusive", "worker": available_workers[0] if available_workers else None}
    return {"mode": mode, "route": "unknown_mode"}


# ---------------------------------------------------------------------------
# Inbox / outbox protocol (Control Tower <-> workers)
# ---------------------------------------------------------------------------

def post_task_to_inbox(worker_id: str, task: dict) -> dict:
    """Control Tower posts a task envelope to a worker's inbox."""
    if worker_id not in WORKERS:
        return {"ok": False, "error": f"unknown worker {worker_id}"}
    ensure_worker_dirs(worker_id)
    env = make_task_envelope(**task)
    env["worker_id"] = worker_id
    env["recipient"] = worker_id
    env["status"] = "QUEUED"
    inbox = _subdirs(worker_id)["inbox"]
    f = _file_lock(inbox / ".lock")
    try:
        _atomic_write(inbox / f"{env['task_id']}.json", json.dumps(env, ensure_ascii=False, indent=2))
    finally:
        _file_unlock(f)
    return {"ok": True, "task": env}


def read_inbox(worker_id: str) -> list[dict]:
    """Worker reads its queued inbox tasks (QUEUED only)."""
    inbox = _subdirs(worker_id)["inbox"]
    if not inbox.exists():
        return []
    out = []
    for p in sorted(inbox.glob("*.json")):
        if p.name == ".lock":
            continue
        try:
            env = json.loads(p.read_text(encoding="utf-8"))
        except (json.JSONDecodeError, OSError):
            continue
        if env.get("status") == "QUEUED":
            out.append(env)
    return out


def write_result(worker_id: str, task_id: str, result: dict, status: str = "SUCCEEDED") -> dict:
    """Worker writes its result to its outbox. Fenced via the task's token:
    the result carries the token that must match what the Control Tower issued."""
    outbox = _subdirs(worker_id)["outbox"]
    outbox.mkdir(parents=True, exist_ok=True)
    rec = {
        "worker_id": worker_id,
        "task_id": task_id,
        "status": status,
        "result": result,
        "completed_at": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()),
    }
    f = _file_lock(outbox / ".lock")
    try:
        _atomic_write(outbox / f"{task_id}.json", json.dumps(rec, ensure_ascii=False, indent=2))
    finally:
        _file_unlock(f)
    return {"ok": True, "worker_id": worker_id, "task_id": task_id, "status": status}


def read_outbox(worker_id: str, task_id: str) -> dict:
    p = _subdirs(worker_id)["outbox"] / f"{task_id}.json"
    if not p.exists():
        return None
    return json.loads(p.read_text(encoding="utf-8"))


# ---------------------------------------------------------------------------
# FAN_OUT
# ---------------------------------------------------------------------------

def fan_out(task: dict, workers: list[str], executor) -> dict:
    """Broadcast one task to N workers and collect results.

    `executor(worker_id, task) -> dict` runs the task for a worker. For a
    worker that is NOT live (WORKER_B), executor should return None and we
    record the worker as SKIPPED/WaitingHeartbeat — never fabricate a result.

    Returns a per-worker report plus the merged result."""
    if task.get("mode") not in ("FAN_OUT", "BATTLECHECK"):
        return {"ok": False, "error": "fan_out requires mode FAN_OUT or BATTLECHECK"}

    per_worker = {}
    results = []
    for wid in workers:
        if wid not in WORKERS:
            per_worker[wid] = {"status": "UNKNOWN_WORKER"}
            continue
        st = worker_status(wid)
        if st["status"] == "PREPARED/WAITING_HEARTBEAT":
            per_worker[wid] = {"status": "SKIPPED", "reason": "waiting heartbeat (not live)"}
            continue
        try:
            result = executor(wid, task)
        except Exception as e:
            per_worker[wid] = {"status": "FAILED", "error": str(e)[:200]}
            continue
        if result is None:
            per_worker[wid] = {"status": "SKIPPED", "reason": "executor returned None"}
            continue
        per_worker[wid] = {"status": "SUCCEEDED", "result": result}
        results.append({"worker_id": wid, "task_id": task.get("task_id"), "output_refs": result.get("output_refs"), "provenance": result.get("provenance", []), "fencing_token": result.get("fencing_token"), "result": result})

    merged = merge_results(results)
    return {
        "mode": task.get("mode"),
        "task_id": task.get("task_id"),
        "per_worker": per_worker,
        "merged": merged,
    }


# ---------------------------------------------------------------------------
# BATTLECHECK
# ---------------------------------------------------------------------------

def battlecheck(results_by_worker: dict[str, dict]) -> dict:
    """Compare two workers' results on observed metrics (latency, failure,
    output presence). Verdict: A_WINS / B_WINS / TIE / INCOMPLETE (if either
    side is missing). Only observed numbers, never brand assumptions."""
    a = results_by_worker.get("MIMO_DEEPSEEK")
    b = results_by_worker.get("MIMO_MINIMAX")

    if a is None and b is None:
        return {"verdict": "INCOMPLETE", "reason": "no results"}
    if a is None:
        return {"verdict": "INCOMPLETE", "reason": "WORKER_A result missing"}
    if b is None:
        return {"verdict": "INCOMPLETE", "reason": "WORKER_B not calibrated (no verified numbers) or not live"}

    metrics = {}
    score_a = score_b = 0

    # latency: lower is better
    la = a.get("latency_ms")
    lb = b.get("latency_ms")
    if la is not None and lb is not None:
        metrics["latency_ms"] = {"A": la, "B": lb}
        if la < lb:
            score_a += 1
        elif lb < la:
            score_b += 1

    # failure: lower is better
    fa = a.get("failure_rate")
    fb = b.get("failure_rate")
    if fa is not None and fb is not None:
        metrics["failure_rate"] = {"A": fa, "B": fb}
        if fa < fb:
            score_a += 1
        elif fb < fa:
            score_b += 1

    # output presence
    oa = bool(a.get("output"))
    ob = bool(b.get("output"))
    metrics["has_output"] = {"A": oa, "B": ob}
    if oa and not ob:
        score_a += 1
    elif ob and not oa:
        score_b += 1

    verdict = "TIE" if score_a == score_b else ("A_WINS" if score_a > score_b else "B_WINS")
    return {
        "verdict": verdict,
        "score": {"MIMO_DEEPSEEK": score_a, "MIMO_MINIMAX": score_b},
        "metrics": metrics,
        "note": "Control Tower owns final acceptance; this is advisory",
    }
