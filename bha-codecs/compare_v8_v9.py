"""Build v8 vs v9 side-by-side comparison from real JSON results.

Reads v8-vs-v1-corpus.json and v9-vs-v1-corpus.json, outputs:
  - aggregate metrics (top-1, top-3, pick distribution)
  - per-file table: BHA-magic | v8_pred | v9_pred | v8_top3 | v9_top3
  - diff: which files v8 hit but v9 missed, and vice versa
"""
from __future__ import annotations

import json
from pathlib import Path

V8_JSON = Path(r"D:\4\bha-codecs\benchmark\ssp5-recommender-v8\v8-vs-v1-corpus.json")
V9_JSON = Path(r"D:\4\bha-codecs\benchmark\ssp5-recommender-v9\v9-vs-v1-corpus.json")
OUT = Path(r"D:\4\bha-codecs\benchmark\ssp5-recommender-v8\v8_vs_v9_comparison.json")


def main():
    v8 = json.loads(V8_JSON.read_text())
    v9 = json.loads(V9_JSON.read_text())

    # Index by file
    v8_by = {r["file"]: r for r in v8["rows"]}
    v9_by = {r["file"]: r for r in v9["rows"]}
    assert set(v8_by) == set(v9_by), "v8 and v9 file sets differ"

    files = sorted(v8_by)
    n = len(files)

    # ---- aggregate metrics ----
    print("=" * 80)
    print("AGGREGATE METRICS (50 real corpus files, leave-one-out)")
    print("=" * 80)
    v8_t1 = v8["v8_top1_match_bha"]
    v9_t1 = v9["v9_top1_match_bha"]
    v8_t3 = v8["v8_top3_match_bha"]
    v9_t3 = v9["v9_top3_match_bha"]
    print(f"  top-1 matches BHA:    v8={v8_t1}/{n} ({100*v8_t1/n:.1f}%)   v9={v9_t1}/{n} ({100*v9_t1/n:.1f}%)   delta={v9_t1-v8_t1:+d}")
    print(f"  top-3 contains BHA:   v8={v8_t3}/{n} ({100*v8_t3/n:.1f}%)   v9={v9_t3}/{n} ({100*v9_t3/n:.1f}%)   delta={v9_t3-v8_t3:+d}")
    print()

    # Pick distribution
    v8_dist = v8["v8_pick_distribution"]
    v9_dist = v9["v9_pick_distribution"]
    all_codecs = sorted(set(v8_dist) | set(v9_dist))
    print("PICK DISTRIBUTION (how many times each codec was top-1)")
    print(f"  {'codec':<20} {'v8':>5} {'v9':>5} {'delta':>6}")
    print(f"  {'-'*20} {'-'*5} {'-'*5} {'-'*6}")
    for c in all_codecs:
        a = v8_dist.get(c, 0)
        b = v9_dist.get(c, 0)
        print(f"  {c:<20} {a:>5} {b:>5} {b-a:>+6d}")
    print()

    # ---- per-file table ----
    print("=" * 80)
    print("PER-FILE COMPARISON (50 real corpus files)")
    print("=" * 80)
    print(f"  {'file':<40} {'bha':<10} {'v8':<14} {'v9':<14} {'top3 match':<10}")
    print(f"  {'-'*40} {'-'*10} {'-'*14} {'-'*14} {'-'*10}")
    rows = []
    for f in files:
        a = v8_by[f]
        b = v9_by[f]
        bha = a["bha_magic"]
        v8p = a["v8_pred"]
        v9p = b["v9_pred"]
        a3 = a["v8_top3"]
        b3 = b["v9_top3"]
        bha_in = ("v8" if bha in a3 else "  ") + ("v9" if bha in b3 else "  ")
        rows.append({
            "file": f,
            "bha_magic": bha,
            "v8_pred": v8p, "v9_pred": v9p,
            "v8_top3": a3, "v9_top3": b3,
            "v8_match": a["v8_matches_bha"],
            "v9_match": b["v9_matches_bha"],
        })
        flag = ("+" if a["v8_matches_bha"] and b["v9_matches_bha"]
                else "~" if (a["v8_matches_bha"] or b["v9_matches_bha"])
                else "-")
        print(f"  {flag} {f:<38} {bha:<10} {v8p:<14} {v9p:<14} {bha_in}")
    print()

    # ---- diff summary ----
    v8_only = [r["file"] for r in rows if r["v8_match"] and not r["v9_match"]]
    v9_only = [r["file"] for r in rows if r["v9_match"] and not r["v8_match"]]
    both = [r["file"] for r in rows if r["v8_match"] and r["v9_match"]]
    neither = [r["file"] for r in rows if not r["v8_match"] and not r["v9_match"]]

    print("=" * 80)
    print("DIFF SUMMARY")
    print("=" * 80)
    print(f"  both v8 & v9 hit:        {len(both):>3d}/{n}  ({100*len(both)/n:.1f}%)")
    print(f"  v8 hit but v9 missed:    {len(v8_only):>3d}/{n}")
    print(f"  v9 hit but v8 missed:    {len(v9_only):>3d}/{n}")
    print(f"  neither hit:              {len(neither):>3d}/{n}")
    print()
    if v8_only:
        print("  Files v8 got but v9 missed:")
        for f in v8_only:
            print(f"    - {f}: v8={v8_by[f]['v8_pred']} vs v9={v9_by[f]['v9_pred']} (BHA={v8_by[f]['bha_magic']})")
    if v9_only:
        print("  Files v9 got but v8 missed:")
        for f in v9_only:
            print(f"    - {f}: v8={v8_by[f]['v8_pred']} vs v9={v9_by[f]['v9_pred']} (BHA={v9_by[f]['bha_magic']})")

    # Save comparison JSON
    OUT.write_text(json.dumps({
        "v8_metrics": {"top1": v8_t1, "top3": v8_t3, "n": n,
                        "pick_distribution": v8_dist},
        "v9_metrics": {"top1": v9_t1, "top3": v9_t3, "n": n,
                        "pick_distribution": v9_dist},
        "diff": {
            "both_hit": both,
            "v8_only": v8_only,
            "v9_only": v9_only,
            "neither": neither,
        },
        "rows": rows,
    }, indent=2))
    print(f"\n  Full comparison saved to {OUT}")


if __name__ == "__main__":
    main()