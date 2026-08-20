"""LZMA 1M rebuilds benchmark — checkpoint+resume pattern.

Splits 1M rebuilds into 1000 segments of 1000 rebuilds each.
Saves best_per_file after each segment. On resume, loads existing state.

Total work: 1M rebuilds × 50 files × ~0.5ms = ~25 minutes wall-time
(split into segments so it survives interrupt/kill).
"""
from __future__ import annotations

import argparse
import itertools
import json
import lzma
import sys
import time
from pathlib import Path


CHECKPOINT_PATH = Path(r"D:\4\bha-codecs\benchmark\1M-rebuilds.json")
SEGMENT_SIZE = 1000
TOTAL_REBUILDS = 1000000
CORPUS_DIR = Path(r"D:\PROJECT UNIVERSE\01Compression\BHA\TEST")


def load_corpus() -> dict:
    out = {}
    for p in sorted(CORPUS_DIR.glob("*")):
        if p.is_file() and p.name != "manifest.json":
            out[p.name] = p.read_bytes()
    return out


def compress_lzma(data: bytes, preset: int, dict_size: int) -> bytes:
    try:
        return lzma.compress(
            data,
            format=lzma.FORMAT_XZ,
            filters=[{"id": lzma.FILTER_LZMA2, "preset": preset}],
            check=-1,
        )
    except lzma.LZMAError:
        return b""


def build_base_params() -> list:
    presets = list(range(10)) + [lzma.PRESET_EXTREME]
    dict_sizes = [65536, 262144, 1048576, 4194304, 16777216]
    return [
        {"preset": p, "dict_size": d}
        for p, d in itertools.product(presets, dict_sizes)
    ]


def load_state() -> dict:
    if CHECKPOINT_PATH.exists():
        try:
            return json.loads(CHECKPOINT_PATH.read_text(encoding="utf-8"))
        except (json.JSONDecodeError, OSError):
            pass
    return {"segments_done": 0, "best_per_file": {}, "best_overall": None}


def save_state(state: dict) -> None:
    CHECKPOINT_PATH.parent.mkdir(parents=True, exist_ok=True)
    tmp = CHECKPOINT_PATH.with_suffix(".tmp")
    tmp.write_text(json.dumps(state, indent=2), encoding="utf-8")
    tmp.replace(CHECKPOINT_PATH)


def run_segment(seg_idx: int, corpus: dict, base_params: list, state: dict) -> dict:
    """Run one segment (1000 rebuilds)."""
    best_per_file = state["best_per_file"]
    t0 = time.perf_counter()
    for r in range(SEGMENT_SIZE):
        combo = base_params[(seg_idx * SEGMENT_SIZE + r) % len(base_params)]
        for name, data in corpus.items():
            comp = compress_lzma(data, combo["preset"], combo["dict_size"])
            if not comp:
                continue
            ratio = len(comp) / max(len(data), 1) * 100
            current = best_per_file.get(name)
            if current is None or ratio < current["ratio"]:
                best_per_file[name] = {
                    "ratio": round(ratio, 4),
                    "params": combo,
                    "bytes": len(data),
                    "compressed": len(comp),
                    "found_at_segment": seg_idx,
                }
    state["segments_done"] = seg_idx + 1
    state["best_per_file"] = best_per_file
    save_state(state)
    return {"elapsed": round(time.perf_counter() - t0, 1), "segment": seg_idx}


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--until-segment", type=int, default=1000)
    parser.add_argument("--segment-size", type=int, default=SEGMENT_SIZE)
    parser.add_argument("--report", default="")
    args = parser.parse_args()
    corpus = load_corpus()
    if not corpus:
        print("no corpus files")
        return 1
    base_params = build_base_params()
    state = load_state()
    start_seg = state["segments_done"]
    print(f"corpus: {len(corpus)} files")
    print(f"base_params (unique combinations): {len(base_params)}")
    print(f"segments done: {start_seg}")
    print(f"target segments: {args.until_segment}")
    print(f"rebuilds per segment: {args.segment_size}")
    print(f"total rebuilds: {args.until_segment * args.segment_size}")
    print(f"total compressions: {args.until_segment * args.segment_size * len(corpus)}")
    print(f"=== running ===")
    t0 = time.perf_counter()
    for seg in range(start_seg, args.until_segment):
        try:
            result = run_segment(seg, corpus, base_params, state)
        except Exception as e:
            print(f"segment {seg} failed: {e}")
            save_state(state)
            return 1
        elapsed = time.perf_counter() - t0
        total_compressions = (seg + 1) * args.segment_size * len(corpus)
        rate = total_compressions / elapsed if elapsed > 0 else 0
        print(f"  segment {seg+1}/{args.until_segment}: {result['elapsed']}s, total {elapsed:.0f}s, {rate:.0f} compressions/s")
        if (seg + 1) % 50 == 0:
            n_done = len(state["best_per_file"])
            avg_ratio = statistics.mean(v["ratio"] for v in state["best_per_file"].values())
            print(f"  check: {n_done} files, avg best ratio {avg_ratio:.3f}%")
    final = load_state()
    if final["best_per_file"]:
        ratios = [v["ratio"] for v in final["best_per_file"].values()]
        sizes = [v["compressed"] for v in final["best_per_file"].values()]
        print(f"\n=== FINAL ===")
        print(f"segments_done: {final['segments_done']}")
        print(f"files: {len(final['best_per_file'])}")
        print(f"avg best ratio: {sum(ratios)/len(ratios):.3f}%")
        print(f"min best ratio: {min(ratios):.3f}%")
        print(f"max best ratio: {max(ratios):.3f}%")
        print(f"total compressed: {sum(sizes):,} bytes")
        if args.report:
            Path(args.report).parent.mkdir(parents=True, exist_ok=True)
            Path(args.report).write_text(json.dumps(final, indent=2), encoding="utf-8")
            print(f"report written to {args.report}")
    return 0


if __name__ == "__main__":
    import statistics
    sys.exit(main())
