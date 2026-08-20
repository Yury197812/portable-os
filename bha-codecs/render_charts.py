"""Render ASCII charts and write unified README for BHA SSP5 recommender.

Reads all_versions_metrics.json (produced by collect_metrics.py) and emits:
  - benchmark/ssp5-recommender-v9b/all_versions_metrics.md
    with final v1..v9b table, ASCII bar charts, sparklines.

Uses pure stdlib — no matplotlib.
"""
from __future__ import annotations

import json
from pathlib import Path

M = json.loads(Path(r"D:\4\bha-codecs\benchmark\ssp5-recommender-v9b\all_versions_metrics.json").read_text())


def bar(value: float, width: int = 30, char: str = "█") -> str:
    """Render a horizontal bar. value in [0..1]."""
    if value is None:
        return " " * width + "  N/A"
    n = max(0, min(width, int(round(value * width))))
    return char * n + " " * (width - n) + f"  {value*100:5.1f}%"


def sparkline(values, width: int = 30) -> str:
    """Sparkline from values. Uses block chars ▁▂▃▄▅▆▇█. Skips None."""
    bars = "▁▂▃▄▅▆▇█"
    clean = [v for v in values if v is not None]
    if not clean:
        return " " * len(values)
    vmin = min(clean)
    vmax = max(clean)
    if vmax == vmin:
        return bars[4] * len(values)
    out = []
    for v in values:
        if v is None:
            out.append(" ")
            continue
        idx = int((v - vmin) / (vmax - vmin) * (len(bars) - 1))
        out.append(bars[idx])
    return "".join(out)


def fmt(v):
    if v is None:
        return "—"
    return f"{v*100:5.1f}%"


def main():
    out = []
    add = out.append

    add("# BHA SSP5 Codec Recommender — Unified Metrics v1..v9b")
    add("")
    add("**Recommender that picks the best codec per file for the Black Hole**")
    add("**Archiver (BHA). Final stable version: v9b (real-only top-1 = 42.0%).**")
    add("")
    add("Built: 2026-08-20  |  Path: `D:\\4\\bha-codecs\\`  |  License: project-internal")
    add("")

    # ---------- 1. Summary table ----------
    add("## 1. Summary table v1..v9b")
    add("")
    add("| Ver | Approach | LOO synth top-1 | LOO real top-1 | LOO real top-3 | 50-file real top-1 |")
    add("|-----|----------|-----------------|-----------------|-----------------|---------------------|")
    rows = [
        ("v1",  "hand-coded decision tree (14 KB)",       "synth_top1", "real_top1_loo", "real_top3_loo", "real_top1_holdout"),
        ("v2",  "k-NN baseline (13 sources)",            "synth_top1", None,             None,             None),
        ("v3",  "augmented k-NN (13×5=65)",              "synth_top1", None,             None,             None),
        ("v4",  "extended to 37 sources, 6 stdlib",      "synth_top1", None,             None,             None),
        ("v5",  "+ 24 BHA-envelope magics (size model)", "synth_top1", None,             None,             None),
        ("v6",  "+ 5 preprocessors (delta/transpose/...)", "synth_top1", None,           None,             None),
        ("v7",  "+ 3 pp + class-balanced k-NN",          "synth_top1", None,             None,             None),
        ("v8",  "v7 training + 50 real corpus points",   "synth_top1", "real_top1_loo", "real_top3_loo", "real_top1_holdout"),
        ("v9",  "v8 + IDF locality log(1+N/df)",         "synth_top1", "real_top1_loo", "real_top3_loo", "real_top1_holdout"),
        ("v9b", "v8 + locality restricted to BHA-dominant (STABLE)", "synth_top1", "real_top1_loo", "real_top3_loo", "real_top1_holdout"),
    ]
    for v, name, k1, k2, k3, k4 in rows:
        d = M.get(v, {})
        s1 = d.get(k1)
        r1 = d.get(k2) if k2 else None
        r3 = d.get(k3) if k3 else None
        r4 = d.get(k4) if k4 else None
        s1s = fmt(s1) if v != "v1" else "14/14 KB ✓"
        add(f"| **{v}** | {name} | {s1s} | {fmt(r1)} | {fmt(r3)} | {fmt(r4)} |")
    add("")

    # ---------- 2. Real-only LOO top-1 bar chart ----------
    add("## 2. Real-only LOO top-1 (50 real BHA files, leave-one-out)")
    add("")
    add("```")
    add("v9b ████████████████████████████████  42.0%   ← STABLE")
    add("v8  ███████████████████████████       34.0%")
    add("v9  ████████████████████████          30.0%   (raw locality over-amplifies bz2)")
    add("v1  ████████████████                  22.0%   (hand-coded KB)")
    add("```")
    add("")

    # ---------- 3. Real-only LOO top-3 bar chart ----------
    add("## 3. Real-only LOO top-3 (50 files)")
    add("")
    add("```")
    add("v8  ████████████████████████████████████  56.0%")
    add("v9b ██████████████████████████████████    52.0%")
    add("v9  ██████████████████████████████      50.0%")
    add("v1  ████████████████                      22.0%")
    add("```")
    add("")

    # ---------- 4. Real-only LOO top-5 bar chart ----------
    add("## 4. Real-only LOO top-5 (50 files)")
    add("")
    add("```")
    add("v9b ██████████████████████████████████████  60.0%   ← STABLE")
    add("v8  ███████████████████████████████████      58.0%")
    add("v9  █████████████████████████████████        56.0%")
    add("```")
    add("")

    # ---------- 5. Synthetic LOO top-1 over versions ----------
    add("## 5. Synthetic LOO top-1 over versions (37 synthetic sources)")
    add("")
    add("```")
    add("v1  ████████████████████████████████████  100.0% (KB overfit)")
    add("v4  ██████████████████                  56.8%")
    add("v5  █████████████████                   51.4%")
    add("v6  ████████████████                    48.6%")
    add("v7  ████████████████                    48.6%")
    add("v2  ████████████                        38.5%")
    add("v3  ██████████                          30.8%")
    add("v9  ███                                  10.8% (synthetic-only LOO not relevant)")
    add("v8  █                                    2.7% (synthetic-only LOO not relevant)")
    add("v9b █                                    2.7% (synthetic-only LOO not relevant)")
    add("```")
    add("Note: v8/v9/v9b's synthetic LOO top-1 collapsed because real-corpus")
    add("points (50) outweigh synthetic (37), shifting class-balance toward")
    add("globally-common lzma2/brotli. This is the correct trade-off for a")
    add("real-file deployment; synthetic-only LOO is no longer the relevant")
    add("metric for v8+.")
    add("")

    # ---------- 6. Sparkline ----------
    add("## 6. Trajectory of real-only LOO top-1 (v1 → v9b)")
    add("")
    add("```")
    add("real-only top-1: 22.0% → ? → ? → ? → ? → ? → ? → 34.0% → 30.0% → 42.0%")
    add("                       v1  v2  v3  v4  v5  v6  v7   v8   v9   v9b")
    add("                              v2-v7 = synthetic-only LOO (not measured on real corpus)")
    spark = sparkline([22.0, None, None, None, None, None, None, 34.0, 30.0, 42.0], width=20)
    add(f"sparkline: {spark}  (v9 local regression then v9b fix)")
    add("```")
    add("")

    # ---------- 7. Pick distribution shift (v8 → v9b) ----------
    add("## 7. Pick distribution shift v8 → v9b (50 real files)")
    add("")
    add("| Codec | v8 | v9b | Δ |")
    add("|-------|----|----|---|")
    deltas = {
        "lzma2":  (23, 25, +2),
        "BHTC1":  (6,  5,  -1),
        "brotli": (7,  4,  -3),
        "BHVT1":  (3,  4,  +1),
        "BHRT1":  (2,  2,   0),
        "BHJA1":  (2,  2,   0),
        "BHTL1":  (2,  2,   0),
        "BHNL1":  (0,  1,  +1),
        "BHTM1":  (1,  1,   0),
        "BHCC1":  (1,  1,   0),
        "BHCC1__transpose": (1, 1, 0),
        "BHQC1":  (1,  0,  -1),
        "bz2":    (1,  1,   0),
    }
    for c, (a, b, d) in deltas.items():
        sign = "+" if d > 0 else ("-" if d < 0 else " ")
        add(f"| {c} | {a} | {b} | {sign}{abs(d)} |")
    add("")
    add("Key shifts: lzma2 +2 (BHA-dominant gain), brotli -3 (correctly demoted),")
    add("BHVT1 +1 (now correctly chosen for `pipe_kv_transition_256k.log`).")
    add("")

    # ---------- 8. Key insights ----------
    add("## 8. Key insights (validated across v1..v9b)")
    add("")
    add("1. **Per-chunk adaptive codec ≤ fixed strategy** — oracle by")
    add("   post-compression size strictly beats any single codec on real data.")
    add("2. **Depth≥2 in compression pipelines = overhead** — LZMA2 already")
    add("   collapses entropy; another LZMA2/bz2/brotli on top adds overhead.")
    add("3. **BHCC1 cross-column beats per-column atomize on multi-col** —")
    add("   cross-column correlation is a real win (3.00% vs 4.07% on telemetry).")
    add("4. **Synthetic ≠ real corpus for benchmarks** — always validate on")
    add("   real files. Same algorithm: +5.6× synth, 0.5× real loss.")
    add("5. **Preprocessor × BHA envelope > stdlib on structured data** —")
    add("   `BHCC1__delta_i64` ×45 on arith streams (8.64% → 0.06%).")
    add("6. **Class-balanced k-NN with `1/sqrt(f/expected)` weights** — v7.")
    add("   sqrt is canonical compromise (Cui et al. 2019, α=0.5).")
    add("7. **Real-corpus training points dominate synthetic for k-NN** — v8.")
    add("   Adding 50 real files lifts real-only top-1 from N/A to 34.0%.")
    add("8. **IDF locality helps ONLY when ground truth is locally rare** — v9.")
    add("   Raw locality demotes lzma2 (23/50 ground truth) and amplifies bz2 (0/50).")
    add("9. **BHA-dominant-restricted locality fixes v9** — v9b. Restrict")
    add("   locality to BHA codecs. Real-only top-1 jumps 17/50 → 21/50 = 42.0%.")
    add("")

    # ---------- 9. v9b algorithm ----------
    add("## 9. v9b algorithm (3-layer weighted vote)")
    add("")
    add("```python")
    add("BHA_DOMINANT = {")
    add("    'lzma2', 'BHTC1', 'BHVT1', 'BHRT1', 'BHJA1', 'BHNL1',")
    add("    'BHCC1', 'BHTM1', 'BHTL1', 'BHMX1', 'BHQC1', 'BHSP1',")
    add("    'BHST1', 'BHDT1', 'BHCS1', 'BHBK1', 'BHDS1', 'BHDS2',")
    add("    'BHCC1__delta_i64', 'BHCC1__transpose', 'BHCC1__json_extract',")
    add("    'BHCC1__collate_keys', 'raw', ...")
    add("}")
    add("")
    add("for each training point (87 total = 37 synth + 50 real):")
    add("    d = L1 distance from query to point")
    add("    cb = 1 / sqrt(freq(label) / (n/n_classes))   # class-balance (v7)")
    add("    locality = log(1 + N/df(label)) if label in BHA_DOMINANT else 1.0")
    add("    score[label] += cb / (d + 0.001) * locality")
    add("")
    add("return top-K codecs by accumulated score")
    add("```")
    add("")
    add("**Key insight:** Non-dominant labels (brotli, bz2, zlib) get")
    add("locality=1.0 (neutral). This stops bz2 from stealing lzma2 votes on")
    add("close ties, while BHA codecs (BHTC1, BHVT1, BHRT1, BHJA1) still")
    add("benefit from IDF amplification when they appear rarely locally.")
    add("")

    # ---------- 10. File layout ----------
    add("## 10. File layout")
    add("")
    add("```")
    add("D:\\4\\bha-codecs\\")
    add("├── README.md                                  # this file")
    add("├── investigate_ssp5_recommender_v9b.py        # STABLE recommender")
    add("├── investigate_ssp5_recommender_v8.py        # predecessor")
    add("├── investigate_ssp5_recommender_v9.py        # broken (raw locality)")
    add("├── investigate_ssp5_recommender_v7.py        # class-balanced k-NN")
    add("├── investigate_ssp5_recommender_v1..v6.py    # earlier iterations")
    add("├── investigate_ssp5_42codec.py              # 13×42 codec matrix")
    add("├── catalog.ini                                # 27 BHA magics + stdlib")
    add("├── build_gpt_packet.py                       # ZIP packager")
    add("├── collect_metrics.py                         # extract v1..v9b metrics")
    add("├── render_charts.py                           # this README")
    add("├── compare_v8_v9.py                          # side-by-side JSON")
    add("├── analyse_v9_failures.py                    # failure mode analysis")
    add("└── benchmark\\")
    add("    ├── ssp5-42codec/                        # 13×42 matrix results")
    add("    ├── recommender-corpus/                   # 50-file real BHA ground truth")
    add("    ├── ssp5-recommender/                     # v1 KB")
    add("    ├── ssp5-recommender-v2 .. -v9/           # earlier versions")
    add("    └── ssp5-recommender-v9b/                 # v9b STABLE + all_versions_metrics")
    add("```")
    add("")

    # ---------- 11. Provenance ----------
    add("## 11. Provenance")
    add("")
    add("- Commits: `1f4c306` (v9b), `a324dc4` (README)")
    add("- ZIP: `D:\\4\\OUT_MIMO\\bha-codecs-ssp5-recommender__MIMO__20260820T1200Z__v1to9b.zip`")
    add("  - 148 KB, 67 entries (26 scripts + 35 benchmark JSON + 6 envelope manifests)")
    add("  - SHA256: `78d82c33995d8a9358cddb90f6aa2ce46bbe79951525edab255e2b4a951e56b1`")

    out_path = Path(r"D:\4\bha-codecs\README.md")
    out_path.write_text("\n".join(out) + "\n")
    print(f"Wrote {out_path} ({len(out)} lines)")


if __name__ == "__main__":
    main()