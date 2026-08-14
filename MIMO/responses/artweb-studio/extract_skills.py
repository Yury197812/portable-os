"""Extract the real skill inventory from the Orchestra worker registry into
skills.seed.json (consumed by the ArtWeb Studio Skills Registry module)."""
import json
from pathlib import Path

REG = Path(r"D:\4\OUT\MIMO\outbox\WORKER-REGISTRY.json")
data = json.loads(REG.read_text(encoding="utf-8"))
workers = data.get("workers", [])

INFRA = {"now-iso", "sha16", "mtime", "ui-operator", "ui-chain", "dashboard-guard",
         "genome-diff", "lean-verify", "device-adapter", "skill-validator",
         "skill-atom-generator", "yaml-to-skill"}


def category(wid):
    if wid.startswith("recursive-"): return "recursive"
    if wid.startswith("skill-mesh-"): return "mesh"
    if wid.startswith("batch-"): return "batch"
    if wid.startswith("habr") or wid.startswith("markdown-to-habr"): return "habr"
    if wid.startswith("oculus"): return "oculus"
    if wid.startswith("artweb"): return "artweb"
    if wid in INFRA: return "инфра"
    return "general"


out = []
for w in workers:
    out.append({
        "n": w.get("id"),
        "cat": category(w.get("id", "")),
        "t": (w.get("triggers") or [])[:3],
        "desc": (w.get("description") or ""),
        "priority": w.get("priority"),
    })

dest = Path(__file__).parent / "skills.seed.json"
dest.write_text(json.dumps(out, ensure_ascii=False, indent=1), encoding="utf-8")
print("extracted", len(out), "skills ->", dest)
