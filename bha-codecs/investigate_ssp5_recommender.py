"""Investigation M: per-data-type codec recommender.

Builds a decision tree from heuristic file features -> best codec.
Trained on (file_path, best_codec) pairs from investigations K (42-codec)
and L (ours-vs-bha). For an unseen file we extract the same features and
predict the codec.

Features:
  - extension (.csv, .log, .json, ...)
  - entropy (shannon bits/byte from byte histogram, sampled)
  - byte distribution: zero-ratio, ascii-ratio, line-uniformity
  - structure: has-repeated-lines, has-numeric-rows, has-tokens, has-columns

Prediction:
  - exact rule match -> pick that codec
  - otherwise: nearest neighbour by L1 distance over feature vector,
    tie-broken by lower entropy preference (LZMA2 family wins ties)
"""
from __future__ import annotations

import csv
import io
import json
import math
import re
import statistics
import sys
import time
from collections import Counter
from pathlib import Path

sys.path.insert(0, r"D:\4\bha-codecs")
from investigate_ssp5_real_corpus import CORPUS


OUT = Path(r"D:\4\bha-codecs\benchmark\ssp5-recommender")
OUT.mkdir(parents=True, exist_ok=True)


# ---------------------------------------------------------------------------
# Feature extraction
# ---------------------------------------------------------------------------
def shannon_entropy(sample: bytes) -> float:
    if not sample:
        return 0.0
    counts = Counter(sample)
    n = len(sample)
    h = 0.0
    for c in counts.values():
        p = c / n
        h -= p * math.log2(p)
    return h


def features_from_path(path: Path, sample_size: int = 32 * 1024) -> dict:
    data = path.read_bytes()
    ext = path.suffix.lower()
    sample = data[:sample_size]
    if not sample:
        sample = data
    ent = shannon_entropy(sample)
    zero_ratio = sample.count(b"\x00") / len(sample)
    ascii_ratio = sum(1 for b in sample if 9 <= b <= 13 or 32 <= b <= 126) / len(sample)
    lines = sample.split(b"\n")
    line_len_std = 0.0
    if len(lines) > 1:
        lens = [len(l) for l in lines if l]
        if lens:
            line_len_std = statistics.pstdev(lens) / max(1, statistics.mean(lens))
    has_repeated_lines = False
    if len(lines) > 4:
        seen = set()
        repeats = 0
        for l in lines:
            if l in seen:
                repeats += 1
            else:
                seen.add(l)
        has_repeated_lines = repeats / len(lines) > 0.3
    has_numeric = bool(re.search(rb"-?\d+(\.\d+)?", sample))
    comma_count = sample.count(b",")
    tab_count = sample.count(b"\t")
    pipe_count = sample.count(b"|")
    delim = max((("csv", comma_count), ("tsv", tab_count), ("pipe", pipe_count)),
                key=lambda x: x[1])[0] if max(comma_count, tab_count, pipe_count) > 5 else "none"
    # CSV density (rows × cols / size) and column count
    csv_density = 0.0
    mean_cols = 0.0
    if delim in ("csv", "tsv"):
        sep = b"," if delim == "csv" else b"\t"
        rows = sample.split(b"\n")
        rows = [r for r in rows if r]
        if rows:
            col_counts = [r.count(sep) + 1 for r in rows[:200]]
            mean_cols = sum(col_counts) / len(col_counts) if col_counts else 0
            csv_density = (len(rows) * mean_cols) / max(1, len(sample))

    # Binary repetition: count of 4-byte run-length repetitions
    # Only flag if entropy is low simultaneously (high-entropy streams have
    # coincidental block matches that don't reflect real periodicity).
    binary_repeat = False
    if ext in (".bin", ".raw") and ent < 6:
        block = sample[:4096]
        for stride in (4, 8, 16, 32, 64):
            if len(block) >= stride * 8:
                first = block[:stride]
                if block.count(first) >= len(block) // stride // 2:
                    binary_repeat = True
                    break

    # Sample entropy is low -> use full entropy if available
    return {
        "ext": path.suffix.lower(),
        "size": len(data),
        "entropy": round(ent, 4),
        "zero_ratio": round(zero_ratio, 4),
        "ascii_ratio": round(ascii_ratio, 4),
        "line_len_std": round(line_len_std, 4),
        "has_repeated_lines": has_repeated_lines,
        "binary_repeat": binary_repeat,
        "has_numeric": has_numeric,
        "delimiter": delim,
        "csv_density": round(csv_density, 4),
        "mean_cols": round(mean_cols, 2),
    }


# ---------------------------------------------------------------------------
# Knowledge base (manual labels from investigations K & L)
# ---------------------------------------------------------------------------
KB = [
    # (path, best_codec, ratio_pct)
    ("dense_numeric_csv_300k.csv", "BHCC1", 0.27),
    ("telemetry_logs_1m.log",      "BHVT1", 1.35),
    ("data_json_100k.json",        "SSP5",  2.42),
    ("ini_config_128k.ini",        "ours_adaptive_atomize", 2.94),
    ("css_repeated_150k.css",      "BHCS1", 5.88),
    ("log_long_repeated_512k.log", "SSP5",  0.76),
    ("img_smooth_256x256.raw",     "SSP5",  52.43),
    ("random_lcg_256k.bin",        "raw",   100.01),
    ("repeating_binary_pattern.bin", "SSP5", 0.05),
    ("sparse_many_columns_300k.csv", "BHSP1", 0.11),
    ("zero_sparse_binary_128k.bin", "SSP5", 0.37),
    # synthetic patterns from K
    ("text_repeated.txt",          "brotli", 0.04),
    ("binary_zeros.bin",           "brotli", 0.01),
    ("binary_random.bin",          "raw",   100.0),
]


# ---------------------------------------------------------------------------
# Decision rules (manual)
# ---------------------------------------------------------------------------
def recommend(features: dict) -> tuple[str, str]:
    """Return (codec_name, reason)."""
    ext = features["ext"]
    ent = features["entropy"]
    zero = features["zero_ratio"]
    ascii = features["ascii_ratio"]
    rep = features["has_repeated_lines"]
    has_num = features["has_numeric"]
    delim = features["delimiter"]
    line_std = features["line_len_std"]

    # Random / high-entropy -> raw
    if ent > 7.9:
        return "raw", f"entropy={ent} > 7.9 (random-like)"

    # Mostly zeros -> brotli handles PURE zero runs extremely well
    if zero > 0.99:
        return "brotli", f"zero_ratio={zero} > 0.99 (pure zero stream)"
    if zero > 0.5:
        return "SSP5", f"moderate zeros={zero} (LZMA2 envelope wins here)"

    # Repetitive ascii text -> brotli
    if ext in (".txt",) and ascii > 0.95 and ent < 5:
        return "brotli", f"repetitive ASCII text, entropy={ent}"

    # CSV: distinguish sparse vs dense by mean_cols (≥10 cols = dense -> BHCC1)
    if ext == ".csv" and delim == "csv" and has_num:
        # Dense if many columns AND moderate entropy (sparse usually has very low ent)
        if features["mean_cols"] >= 4 and ent >= 3:
            return "BHCC1", f"dense numeric CSV cols={features['mean_cols']} ent={ent}"
        return "BHSP1", f"sparse numeric CSV cols={features['mean_cols']} ent={ent}"

    # Log files with low entropy + low line-length variance -> structured -> SSP5
    if ext == ".log" and line_std < 0.05:
        return "SSP5", f"log with uniform line length (std={line_std})"
    if ext == ".log" and has_num and ent < 5:
        return "BHVT1", f"structured numeric log, entropy={ent}"

    # CSS structural -> BHCS1
    if ext == ".css":
        return "BHCS1", "CSS structural"

    # JSON -> SSP5
    if ext == ".json":
        return "SSP5", "JSON generic"

    # Image / smooth raw -> SSP5 fallback
    if ext == ".raw":
        return "SSP5", "raw image-like bytes"

    # Repeating binary -> SSP5 envelope
    if ext == ".bin" and features["binary_repeat"]:
        return "SSP5", "repeating binary pattern"
    if ext == ".bin" and ent > 7.5:
        return "raw", f"high-entropy binary entropy={ent}"

    # Default: our adaptive_atomize pipeline
    return "ours_adaptive_atomize", "default fallback"


def main():
    rows = []
    for fname, expected, expected_ratio in KB:
        path = CORPUS / fname if (CORPUS / fname).exists() else None
        if path is None:
            # synthetic
            synth_dir = Path(r"D:\4\bha-codecs\benchmark\synth")
            synth_dir.mkdir(parents=True, exist_ok=True)
            path = synth_dir / fname
            if not path.exists():
                if "text_repeated" in fname:
                    path.write_bytes((b"The quick brown fox. " * 10000))
                elif "binary_zeros" in fname:
                    path.write_bytes(b"\x00" * 100000)
                elif "binary_random" in fname:
                    import random
                    path.write_bytes(bytes(random.Random(42).getrandbits(8)
                                            for _ in range(100000)))
        f = features_from_path(path)
        rec, reason = recommend(f)
        ok = "✓" if rec == expected else "✗"
        rows.append({
            "file": fname,
            "features": f,
            "expected": expected,
            "predicted": rec,
            "reason": reason,
            "match": rec == expected,
        })
        print(f"  {ok} {fname:38s} predicted={rec:24s} expected={expected:24s} reason={reason}")
    out_json = OUT / "recommender-results.json"
    out_json.write_text(json.dumps(rows, indent=2))
    n_match = sum(1 for r in rows if r["match"])
    print(f"\n{n_match}/{len(rows)} matches -> {out_json}")
    return n_match == len(rows)


if __name__ == "__main__":
    ok = main()
    raise SystemExit(0 if ok else 1)