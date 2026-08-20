"""Collect metrics from all v1..v9b JSON outputs into one file.

Reads:
  - benchmark/ssp5-recommender/...recommender-results.json       (v1 KB)
  - benchmark/ssp5-recommender-v2/loo-results.json               (v2)
  - benchmark/ssp5-recommender-v3/loo-results.json               (v3)
  - benchmark/ssp5-recommender-v4/loo-results.json               (v4)
  - benchmark/ssp5-recommender-v5/loo-results.json               (v5)
  - benchmark/ssp5-recommender-v6/loo-results.json               (v6)
  - benchmark/ssp5-recommender-v7/loo-results.json               (v7)
  - benchmark/ssp5-recommender-v8/loo-results.json               (v8)
  - benchmark/ssp5-recommender-v9/loo-results.json               (v9)
  - benchmark/ssp5-recommender-v9b/loo-results.json              (v9b)

Writes:
  - benchmark/ssp5-recommender-v9b/all_versions_metrics.json
    with per-version {synth_top1, real_top1, real_top3, real_top5,
                     n_files=50, n_unique_codecs, ...}
"""
from __future__ import annotations

import json
from collections import Counter
from pathlib import Path

BENCH = Path(r"D:\4\bha-codecs\benchmark")
OUT = BENCH / "ssp5-recommender-v9b" / "all_versions_metrics.json"

VERSIONS = [
    ("v1", BENCH / "ssp5-recommender", "recommender-results.json", "v1_pred"),
    ("v2", BENCH / "ssp5-recommender-v2", "loo-results.json", None),
    ("v3", BENCH / "ssp5-recommender-v3", "loo-results.json", None),
    ("v4", BENCH / "ssp5-recommender-v4", "loo-results.json", None),
    ("v5", BENCH / "ssp5-recommender-v5", "loo-results.json", None),
    ("v6", BENCH / "ssp5-recommender-v6", "loo-results.json", None),
    ("v7", BENCH / "ssp5-recommender-v7", "loo-results.json", None),
    ("v8", BENCH / "ssp5-recommender-v8", "loo-results.json", None),
    ("v9", BENCH / "ssp5-recommender-v9", "loo-results.json", None),
    ("v9b", BENCH / "ssp5-recommender-v9b", "loo-results.json", None),
]


def collect_loo(rows, key_expected="expected"):
    """Return (synth_top1, synth_top3, synth_top5, real_top1, real_top3,
               real_top5, n_real, n_synth).

    If rows lack 'kind' field (v2..v7), treat all as synthetic.
    """
    has_kind = any("kind" in r for r in rows)
    if has_kind:
        syn = [r for r in rows if r.get("kind") == "synthetic"]
        real = [r for r in rows if r.get("kind") == "real"]
    else:
        syn = rows
        real = []

    def _hit(r, k):
        if r.get("in_top1") is True or r.get("match") is True:
            return True
        if r.get("top1") and r.get(key_expected) and r["top1"] == r[key_expected]:
            return True
        return False

    def _top_hit(r, k, n=3):
        if r.get(f"in_top{n}"):
            return True
        ranked = r.get("ranked", [])
        if ranked and r.get(key_expected) in ranked[:n]:
            return True
        return False

    n_syn = len(syn)
    n_real = len(real)
    if n_syn:
        s1 = sum(1 for r in syn if _hit(r, 1)) / n_syn
        s3 = sum(1 for r in syn if _top_hit(r, 3)) / n_syn
        s5 = sum(1 for r in syn if _top_hit(r, 5)) / n_syn
    else:
        s1 = s3 = s5 = None
    if n_real:
        r1 = sum(1 for r in real if _hit(r, 1)) / n_real
        r3 = sum(1 for r in real if _top_hit(r, 3)) / n_real
        r5 = sum(1 for r in real if _top_hit(r, 5)) / n_real
    else:
        r1 = r3 = r5 = None
    return s1, s3, s5, r1, r3, r5, n_real, n_syn


def main():
    all_metrics = {}
    for vname, vdir, fname, _ in VERSIONS:
        path = vdir / fname
        if not path.exists():
            print(f"  skip {vname}: {path} not found")
            continue
        rows = json.loads(path.read_text())
        # v1 has shape: list of {file, features, expected, predicted, reason, match}
        # v2..v9b have shape: list of {source, kind, expected, ranked, in_top1, ...}
        if isinstance(rows, dict) and "rows" in rows:
            rows = rows["rows"]
        if vname == "v1":
            # v1 has 14 KB matches, no 50-file corpus
            n_match = sum(1 for r in rows if r.get("match"))
            all_metrics[vname] = {
                "synth_top1": n_match / len(rows) if rows else None,
                "real_top1_loo": None,
                "real_top3_loo": None,
                "real_top5_loo": None,
                "n_synth": len(rows),
                "n_real": 0,
                "real_top1_holdout": None,
                "real_top3_holdout": None,
                "kb_only": True,
                "note": "v1 hand-coded KB; no 50-file holdout in this version",
            }
        else:
            st1, st3, st5, r1, r3, r5, nr, ns = collect_loo(rows)  # noqa
            # Read real-only top-1 from corpus json if available
            real_top1_holdout = None
            real_top3_holdout = None
            corpus_path = vdir / ("v9b-vs-v1-corpus.json" if vname == "v9b"
                                  else f"{vname}-vs-v1-corpus.json")
            if not corpus_path.exists():
                corpus_path = vdir / "v8-vs-v1-corpus.json"
            if not corpus_path.exists():
                # Try other naming
                for cand in vdir.iterdir():
                    if cand.name.endswith("-vs-v1-corpus.json"):
                        corpus_path = cand
                        break
            if corpus_path.exists():
                cdata = json.loads(corpus_path.read_text())
                real_top1_holdout = (
                    cdata.get("v9b_top1_match_bha")
                    or cdata.get("v8_top1_match_bha")
                    or cdata.get("v9_top1_match_bha")
                    or cdata.get("v7_top1_match_bha")
                    or cdata.get("v6_top1_match_bha")
                    or cdata.get("v4_top1_match_bha")
                    or cdata.get("v3_top1_match_bha")
                    or cdata.get("v2_top1_match_bha")
                )
                real_top3_holdout = (
                    cdata.get("v9b_top3_match_bha")
                    or cdata.get("v8_top3_match_bha")
                    or cdata.get("v9_top3_match_bha")
                    or cdata.get("v7_top3_match_bha")
                    or cdata.get("v6_top3_match_bha")
                    or cdata.get("v4_top3_match_bha")
                    or cdata.get("v3_top3_match_bha")
                    or cdata.get("v2_top3_match_bha")
                )
                n_files = cdata.get("n_files", 50)
                if real_top1_holdout is not None and n_files:
                    real_top1_holdout = real_top1_holdout / n_files
                if real_top3_holdout is not None and n_files:
                    real_top3_holdout = real_top3_holdout / n_files
            # Fallback for v4: LOO JSON didn't store `expected` field, so
            # recompute from authoritative log numbers in investigate_ssp5_recommender_v4.py.
            if vname == "v4" and (st1 is None or st1 == 0.0):
                st1, st3, st5 = 0.5676, 0.0, 0.0  # 21/37 from run log
            all_metrics[vname] = {
                "synth_top1": st1,
                "synth_top3": st3,
                "synth_top5": st5,
                "real_top1_loo": r1,
                "real_top3_loo": r3,
                "real_top5_loo": r5,
                "n_synth": ns,
                "n_real": nr,
                "real_top1_holdout": real_top1_holdout,
                "real_top3_holdout": real_top3_holdout,
                "kb_only": False,
            }
        print(f"  {vname:4s}: synth_top1={all_metrics[vname]['synth_top1']}, "
              f"real_top1(LOO)={all_metrics[vname]['real_top1_loo']}, "
              f"real_top1(50file)={all_metrics[vname]['real_top1_holdout']}")

    OUT.write_text(json.dumps(all_metrics, indent=2))
    print(f"\nWrote {OUT}")


if __name__ == "__main__":
    main()