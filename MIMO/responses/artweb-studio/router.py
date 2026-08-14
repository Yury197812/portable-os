"""
router.py — dynamic model routing for ArtWeb Studio.

Routes models by 8 weighted axes:
  quality, latency (lower=better), cost (lower=better), context,
  privacy, availability, tool_use, free.

Loads a catalog (default: models.seed.json) and returns top-N ranked
models. Stdlib-only (matches Orchestra convention).

CLI:
  python router.py route [--top N] [--weights "q=8,lat=3,cost=2,free=8"]
      [--require tool_use,vision] [--modality text] [--locality local] [--json]
  python router.py capabilities
"""

from __future__ import annotations

import argparse
import json
from pathlib import Path

DEFAULT_CATALOG = Path(__file__).parent / "models.seed.json"

AXES = {
    "quality":      ("Quality", True, 10.0),
    "latency":      ("Latency", False, 2500.0),
    "cost":         ("Cost", False, 15.0),
    "context":      ("Context", True, 2000.0),
    "privacy":      ("Privacy", True, 10.0),
    "availability": ("Availability", True, 10.0),
    "tool_use":     ("tool_use", True, 1.0),
    "free":         ("FREE", True, 1.0),
}
DEFAULT_WEIGHTS = {
    "quality": 5, "latency": 5, "cost": 4, "context": 3,
    "privacy": 3, "availability": 3, "tool_use": 5, "free": 2,
}


def load(catalog=None):
    p = Path(catalog) if catalog else DEFAULT_CATALOG
    return json.loads(p.read_text(encoding="utf-8"))


def _norm(v, higher_is_better, mx):
    x = min(1.0, max(0.0, v / mx))
    return x if higher_is_better else 1.0 - x


def score(model, weights=None):
    w = weights or DEFAULT_WEIGHTS
    s = 0.0
    s += w["quality"] * _norm(model.get("quality", 0), True, 10.0)
    s += w["latency"] * _norm(model.get("latency_ms", 0), False, 2500.0)
    s += w["cost"] * (1.0 if model.get("free") else _norm(model.get("cost_per_mtok", 0), False, 15.0))
    s += w["context"] * _norm(model.get("context_k", 0) or 0, True, 2000.0)
    s += w["privacy"] * _norm(model.get("privacy", 5), True, 10.0)
    s += w["availability"] * _norm(model.get("availability", 9), True, 10.0)
    s += w["tool_use"] * (1.0 if model.get("tool_use") else 0.0)
    s += w["free"] * (1.0 if model.get("free") else 0.0)
    return round(s, 3)


def route(models, weights=None, top=5, require=None, modality=None, locality=None):
    caps = set(require or [])
    scored = []
    for m in models:
        if caps and not caps.issubset(set(m.get("capabilities", []))):
            continue
        if modality and m.get("modality") != modality:
            continue
        if locality and m.get("locality") != locality:
            continue
        scored.append((score(m, weights), m))
    scored.sort(key=lambda x: -x[0])
    return scored[:top]


_ALIAS = {"q": "quality", "lat": "latency", "ctx": "context", "priv": "privacy",
          "avail": "availability", "tool": "tool_use"}


def _parse_weights(s):
    w = dict(DEFAULT_WEIGHTS)
    for kv in (s or "").split(","):
        if "=" in kv:
            k, v = kv.split("=", 1)
            k = _ALIAS.get(k.strip(), k.strip())
            if k in w:
                w[k] = float(v.strip())
    return w


def main():
    p = argparse.ArgumentParser(description="ArtWeb Studio dynamic router")
    sub = p.add_subparsers(dest="cmd", required=True)
    pr = sub.add_parser("route")
    pr.add_argument("--top", type=int, default=5)
    pr.add_argument("--weights", default=None, help="e.g. 'q=8,lat=3,cost=2,free=8'")
    pr.add_argument("--require", default=None, help="comma list e.g. 'tool_use,vision'")
    pr.add_argument("--modality", default=None, choices=["text", "image", "audio", "embed"])
    pr.add_argument("--locality", default=None, choices=["cloud", "local", "hybrid"])
    pr.add_argument("--catalog", default=None)
    pr.add_argument("--json", action="store_true")
    sub.add_parser("capabilities")
    args = p.parse_args()

    if args.cmd == "capabilities":
        print(json.dumps(list(AXES.keys()), ensure_ascii=False))
        return 0

    models = load(args.catalog)
    weights = _parse_weights(args.weights) if args.weights else DEFAULT_WEIGHTS
    require = [x.strip() for x in args.require.split(",")] if args.require else None
    res = route(models, weights, args.top, require, args.modality, args.locality)

    if args.json:
        out = [{"rank": i + 1, "score": s, **m} for i, (s, m) in enumerate(res)]
        print(json.dumps(out, ensure_ascii=False, indent=2))
    else:
        for i, (s, m) in enumerate(res, 1):
            free = "FREE" if m["free"] else "     "
            print(f"{i}. {s:6.1f}  {m['name']:<24} {m['provider']:<12} {free}  {','.join(m['capabilities'])}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
