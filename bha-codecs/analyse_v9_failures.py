"""Analyse v8 vs v9 failure modes.

Failure-mode taxonomy (modes where v9 lost vs v8):

  MODE A: v9 picked lzma2 → bz2 (IDF over-amplified bz2 in k-NN ball)
  MODE B: v9 picked brotli   → lzma2 (lost top-1 because locality demoted lzma2)
  MODE C: v9 picked bz2      → lzma2 (same as B)
  MODE D: v9 picked lzma2   → brotli (locality demoted lzma2 in favor of brotli)
  MODE E: v9 picked BHTC1   → BHVT1 (lost exact match for BHVT1)
  MODE F: v9 picked lzma2   → BHNL1 (etc)

Per-mode count + ranked examples.
"""
from __future__ import annotations

import json
from collections import Counter, defaultdict
from pathlib import Path

V8 = Path(r"D:\4\bha-codecs\benchmark\ssp5-recommender-v8\v8-vs-v1-corpus.json")
V9 = Path(r"D:\4\bha-codecs\benchmark\ssp5-recommender-v9\v9-vs-v1-corpus.json")
OUT = Path(r"D:\4\bha-codecs\benchmark\ssp5-recommender-v8\v9_failure_modes.json")


def main():
    v8 = json.loads(V8.read_text())
    v9 = json.loads(V9.read_text())
    v8_by = {r["file"]: r for r in v8["rows"]}
    v9_by = {r["file"]: r for r in v9["rows"]}

    # v8 hit, v9 missed → v9 failure
    failures = []
    for f, a in v8_by.items():
        if a["v8_matches_bha"] and not v9_by[f]["v9_matches_bha"]:
            failures.append({
                "file": f,
                "bha_magic": a["bha_magic"],
                "v8_pred": a["v8_pred"],
                "v9_pred": v9_by[f]["v9_pred"],
                "v8_top3": a["v8_top3"],
                "v9_top3": v9_by[f]["v9_top3"],
                "v8_bha_in_top3": a["v8_bha_in_top3"],
                "v9_bha_in_top3": v9_by[f]["v9_bha_in_top3"],
            })

    # Classify each failure into a mode
    def mode(bha, v8p, v9p):
        if bha == "lzma2":
            if v8p == "lzma2" and v9p == "bz2":
                return "A_lzma2_to_bz2"
            if v8p == "lzma2" and v9p == "brotli":
                return "D_lzma2_to_brotli"
            if v8p == "BHTC1" and v9p == "BHVT1":
                return "E_lost_BHVT1"
            if v8p == "BHTC1" and v9p == "BHNL1":
                return "F_lost_BHNL1"
        if bha == "BHVT1":
            if v8p == "BHTC1" and v9p == "BHVT1":
                return "E_lost_BHVT1"
        return "OTHER"

    by_mode = defaultdict(list)
    for f in failures:
        m = mode(f["bha_magic"], f["v8_pred"], f["v9_pred"])
        by_mode[m].append(f)

    # Print top 5 modes by count
    print("=" * 80)
    print("V9 FAILURE MODES (ranked by frequency)")
    print("=" * 80)
    print(f"{'rank':<5} {'mode':<22} {'count':>5} {'% of all failures':>20}")
    print("-" * 55)
    total_failures = len(failures)
    sorted_modes = sorted(by_mode.items(), key=lambda x: -len(x[1]))
    for i, (m, fs) in enumerate(sorted_modes[:10], 1):
        print(f"{i:<5} {m:<22} {len(fs):>5} {100*len(fs)/total_failures:>19.1f}%")
    print()
    print(f"Total v9 losses: {total_failures}")
    print()

    # For each top mode, show the files
    print("=" * 80)
    print("TOP 5 FAILURE MODES — DETAIL")
    print("=" * 80)
    for i, (m, fs) in enumerate(sorted_modes[:5], 1):
        print(f"\n## Mode #{i}: {m} ({len(fs)} cases)\n")
        print(f"  {'file':<38} {'BHA':<8} {'v8':<10} {'v9':<10} {'v8_top3':<24} {'v9_top3':<24}")
        print(f"  {'-'*38} {'-'*8} {'-'*10} {'-'*10} {'-'*24} {'-'*24}")
        for f in fs:
            print(f"  {f['file']:<38} {f['bha_magic']:<8} {f['v8_pred']:<10} {f['v9_pred']:<10} "
                  f"{','.join(f['v8_top3']):<24} {','.join(f['v9_top3']):<24}")

    # Also save as JSON
    OUT.write_text(json.dumps({
        "total_v9_losses": total_failures,
        "modes_ranked": [
            {"mode": m, "count": len(fs), "files": fs}
            for m, fs in sorted_modes
        ],
    }, indent=2))
    print(f"\n  Full detail saved to {OUT}")


if __name__ == "__main__":
    main()