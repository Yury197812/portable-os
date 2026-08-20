"""Investigation J: multi-algorithm + multi-pass + multi-type codec selector.

Three orthogonal axes:
  Axis 1: Algorithm (per single-pass encoder)
    - raw (identity)
    - atomize (custom centered-delta)
    - adaptive_atomize (per-chunk atomize-vs-raw pick)
    - zlib (level 9)
    - bz2 (level 9)
    - lzma-XZ (extreme)
    - lzma2 (raw, extreme)
    - brotli (level 11)
    - ssp5 (LZMA2 in SSP5 envelope)
    - ssp5(atomize) (atomize then SSP5)
    - ssp5(adaptive_atomize)

  Axis 2: Multi-pass — re-encode the output of a previous pass with another
    algorithm. Tests recursive depth 1..3 with the chosen set.

  Axis 3: Data type — text/binary/numeric/monotonic/random from real BHA TEST
    corpus and synthetic generators.

For each (data_type, algo, depth) tuple we measure size and emit a per-data-type
recommendation. Roundtrip integrity is verified for our custom formats (atomize
families, ssp5 envelope, brotli, bz2, zlib).
"""
from __future__ import annotations

import bz2
import io
import json
import lzma
import os
import struct
import sys
import time
import zlib
from pathlib import Path

sys.path.insert(0, r"D:\4\bha-codecs")
import brotli
from investigate_ssp5_even_atom import (
    atomize_integers, deatomize_integers,
    ssp5_encode, ssp5_decode,
    gen_even_mask_zero, gen_even_mask_one,
    gen_arbitrary, gen_arbitrary_mixed,
)
from investigate_ssp5_adaptive import (
    adaptive_atomize, deadaptive_atomize,
)
from investigate_ssp5_real_corpus import (
    extract_ints_dense_csv, extract_ints_telemetry,
    CORPUS,
)

OUT = Path(r"D:\4\bha-codecs\benchmark\ssp5-multipass")
OUT.mkdir(parents=True, exist_ok=True)


# ---------------------------------------------------------------------------
# Single-pass encoders (data -> bytes, decompress symmetric)
# ---------------------------------------------------------------------------
ENC = {}


def _register(name, enc, dec):
    ENC[name] = (enc, dec)
    return name


def _identity(data: bytes) -> bytes:
    return data


def _zlib(data: bytes) -> bytes:
    return zlib.compress(data, 9)


def _zlib_dec(data: bytes) -> bytes:
    return zlib.decompress(data)


def _bz2(data: bytes) -> bytes:
    return bz2.compress(data, 9)


def _bz2_dec(data: bytes) -> bytes:
    return bz2.decompress(data)


def _lzma_xz(data: bytes) -> bytes:
    return lzma.compress(data, format=lzma.FORMAT_XZ,
                          preset=7 | lzma.PRESET_EXTREME)


def _lzma_xz_dec(data: bytes) -> bytes:
    return lzma.decompress(data, format=lzma.FORMAT_XZ)


def _lzma2_ext(data: bytes) -> bytes:
    best = None
    for p in (6, 9 | lzma.PRESET_EXTREME):
        c = lzma.compress(data, format=lzma.FORMAT_RAW,
                          filters=[{"id": lzma.FILTER_LZMA2, "preset": p}])
        if best is None or len(c) < len(best):
            best = c
    return best


def _lzma2_ext_dec(data: bytes) -> bytes:
    return lzma.decompress(data, format=lzma.FORMAT_RAW,
                            filters=[{"id": lzma.FILTER_LZMA2}])


def _brotli(data: bytes) -> bytes:
    return brotli.compress(data, quality=11)


def _brotli_dec(data: bytes) -> bytes:
    return brotli.decompress(data)


def _atomize_bytes(values: bytes) -> bytes:
    """Atomize a bytes object by treating it as packed int64 little-endian."""
    if len(values) % 8:
        raise ValueError("not multiple of 8")
    n = len(values) // 8
    vals = list(struct.unpack("<" + "q" * n, values))
    return atomize_integers(vals, chunk=4096)


def _atomize_bytes_dec(data: bytes) -> bytes:
    vals = deatomize_integers(data)
    return b"".join(struct.pack("<q", v) for v in vals)


def _adaptive_bytes(values: bytes) -> bytes:
    if len(values) % 8:
        raise ValueError("not multiple of 8")
    n = len(values) // 8
    vals = list(struct.unpack("<" + "q" * n, values))
    return adaptive_atomize(vals, chunk=4096)


def _adaptive_bytes_dec(data: bytes) -> bytes:
    vals = deadaptive_atomize(data)
    return b"".join(struct.pack("<q", v) for v in vals)


def _ssp5(data: bytes) -> bytes:
    return ssp5_encode(data)


def _ssp5_dec(data: bytes) -> bytes:
    return ssp5_decode(data)


def _ssp5_atomize(data: bytes) -> bytes:
    return ssp5_encode(atomize_integers(
        list(struct.unpack("<" + "q" * (len(data) // 8), data)), chunk=4096))


def _ssp5_adaptive(data: bytes) -> bytes:
    return ssp5_encode(adaptive_atomize(
        list(struct.unpack("<" + "q" * (len(data) // 8), data)), chunk=4096))


_register("raw", _identity, _identity)
_register("zlib", _zlib, _zlib_dec)
_register("bz2", _bz2, _bz2_dec)
_register("lzma_xz", _lzma_xz, _lzma_xz_dec)
_register("lzma2_ext", _lzma2_ext, _lzma2_ext_dec)
_register("brotli", _brotli, _brotli_dec)
_register("ssp5", _ssp5, _ssp5_dec)
_register("ssp5_atom", _ssp5_atomize, lambda d: b"".join(
    struct.pack("<q", v) for v in deatomize_integers(ssp5_decode(d))))
_register("ssp5_adapt", _ssp5_adaptive, lambda d: b"".join(
    struct.pack("<q", v) for v in deadaptive_atomize(ssp5_decode(d))))


# Int-only encoders (work on packed u64, can be chained with byte compressors).
def _atomize_only(data: bytes) -> bytes:
    return _atomize_bytes(data)


def _atomize_only_dec(data: bytes) -> bytes:
    return _atomize_bytes_dec(data)


def _adaptive_only(data: bytes) -> bytes:
    return _adaptive_bytes(data)


def _adaptive_only_dec(data: bytes) -> bytes:
    return _adaptive_bytes_dec(data)


_register("atomize", _atomize_only, _atomize_only_dec)
_register("adaptive", _adaptive_only, _adaptive_only_dec)


# ---------------------------------------------------------------------------
# Data sources
# ---------------------------------------------------------------------------
def _read_bytes(path: Path) -> bytes:
    return path.read_bytes()


def _text_repeated(n: int = 200_000) -> bytes:
    """Repetitive English text."""
    base = (b"The quick brown fox jumps over the lazy dog. "
            b"Pack my box with five dozen liquor jugs. ")
    return (base * ((n // len(base)) + 1))[:n]


def _binary_random(n: int = 200_000) -> bytes:
    import random
    rnd = random.Random(42)
    return bytes(rnd.getrandbits(8) for _ in range(n))


def _binary_zeros(n: int = 200_000) -> bytes:
    return b"\x00" * n


def _int_stream(values: list[int]) -> bytes:
    return b"".join(struct.pack("<q", v) for v in values)


SOURCES = {
    "syn_even_0": lambda: _int_stream(gen_even_mask_zero(16_384)),
    "syn_even_1": lambda: _int_stream(gen_even_mask_one(16_384)),
    "syn_arb_lcg": lambda: _int_stream(gen_arbitrary(16_384)),
    "syn_arb_mixed": lambda: _int_stream(gen_arbitrary_mixed(16_384)),
    "real_csv": lambda: _int_stream(extract_ints_dense_csv(
        CORPUS / "dense_numeric_csv_300k.csv", max_rows=16_384)),
    "real_telemetry": lambda: _int_stream(extract_ints_telemetry(
        CORPUS / "telemetry_logs_1m.log", max_rows=16_384)),
    "text_repeated": lambda: _text_repeated(200_000),
    "binary_zeros": lambda: _binary_zeros(200_000),
    "binary_random": lambda: _binary_random(200_000),
    "ini_config": lambda: _read_bytes(CORPUS / "ini_config_128k.ini"),
    "json_array": lambda: _read_bytes(CORPUS / "data_json_100k.json"),
    "css_repeated": lambda: _read_bytes(CORPUS / "css_repeated_150k.css"),
    "telemetry_log_raw": lambda: _read_bytes(CORPUS / "telemetry_logs_1m.log")[:200_000],
}


# ---------------------------------------------------------------------------
# Multi-pass: chain encoders, track the recipe
# ---------------------------------------------------------------------------
def chain_apply(data: bytes, recipe: list[str]) -> bytes:
    cur = data
    for name in recipe:
        enc, _ = ENC[name]
        cur = enc(cur)
    return cur


def chain_decode(data: bytes, recipe: list[str]) -> bytes:
    cur = data
    for name in reversed(recipe):
        _, dec = ENC[name]
        cur = dec(cur)
    return cur


# ---------------------------------------------------------------------------
# Per-data-type selector: pick best recipe (depth <= 3)
# ---------------------------------------------------------------------------
def best_recipe(data: bytes, candidates: list[list[str]]) -> tuple[list[str], int]:
    best_size = None
    best_recipe = None
    for recipe in candidates:
        out = chain_apply(data, recipe)
        if best_size is None or len(out) < best_size:
            best_size = len(out)
            best_recipe = recipe
    return best_recipe, best_size


def candidates_for_int(max_depth: int = 2) -> list[list[str]]:
    """Recipe candidates for integer streams."""
    leaves = ["lzma2_ext", "zlib", "bz2", "brotli", "ssp5", "raw"]
    int_pre = ["atomize", "adaptive", "raw"]
    cands = [[a] for a in leaves + int_pre]
    cands += [["ssp5", a] for a in leaves if a != "raw"]  # ssp5 then compress
    cands += [[a, "ssp5"] for a in int_pre if a != "raw"]  # prep then ssp5
    cands += [["ssp5_atom"], ["ssp5_adapt"]]
    if max_depth >= 2:
        cands += [["ssp5", "zlib"], ["ssp5", "bz2"]]
        cands += [["atomize", "lzma2_ext"], ["adaptive", "lzma2_ext"]]
    return cands


def candidates_for_bytes(max_depth: int = 2) -> list[list[str]]:
    leaves = ["lzma_xz", "lzma2_ext", "zlib", "bz2", "brotli", "ssp5", "raw"]
    cands = [[a] for a in leaves]
    cands += [["ssp5", a] for a in ["zlib", "bz2"]]
    if max_depth >= 2:
        cands += [["zlib", "bz2"], ["bz2", "zlib"]]
        cands += [["ssp5", "zlib", "bz2"]]
    return cands


# ---------------------------------------------------------------------------
# Main
# ---------------------------------------------------------------------------
def main():
    results = []
    rt_checks = []
    for sname, sfn in SOURCES.items():
        data = sfn()
        is_int_stream = sname.startswith(("syn_", "real_"))
        cands = candidates_for_int() if is_int_stream else candidates_for_bytes()
        recipe, best_size = best_recipe(data, cands)
        chain_str = " -> ".join(recipe)
        # roundtrip
        try:
            dec = chain_decode(ssp5_encode(data) if False else chain_apply(data, recipe), recipe)
            match = dec == data
        except Exception as e:
            match = False
            chain_str = f"{chain_str} (decode-fail: {e})"
        rt_checks.append({"source": sname, "recipe": recipe, "match": match})
        # size of every single-pass candidate (for report)
        singles = []
        for cand in set(tuple(c) for c in cands if len(c) == 1):
            n = cand[0]
            try:
                sz = len(chain_apply(data, [n]))
                singles.append((n, sz))
            except Exception:
                pass
        singles.sort(key=lambda x: x[1])
        results.append({
            "source": sname,
            "orig": len(data),
            "best_recipe": recipe,
            "best_chain": chain_str,
            "best_size": best_size,
            "ratio_pct": round(100 * best_size / max(1, len(data)), 2),
            "top_singles": singles[:5],
        })
        print(f"\n{sname}: orig={len(data)}")
        print(f"  singles (top 5): {singles[:5]}")
        print(f"  best recipe: {chain_str}  size={best_size}  "
              f"ratio={100 * best_size / max(1, len(data)):.2f}%")
    print("\n--- Roundtrip integrity ---")
    for r in rt_checks:
        flag = "OK" if r["match"] else "FAIL"
        print(f"  [{flag}] {r['source']:18s} {' -> '.join(r['recipe'])}")
    fails = [r for r in rt_checks if not r["match"]]
    if fails:
        print(f"\nROUNDTRIP FAILED on {len(fails)}: {[f['source'] for f in fails]}")
        raise SystemExit(1)
    out_json = OUT / "multipass-results.json"
    out_json.write_text(json.dumps({
        "results": results, "roundtrip": rt_checks,
    }, indent=2))
    print(f"\nresults -> {out_json}")


if __name__ == "__main__":
    main()