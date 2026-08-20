"""Investigation K: 30+ BHA codec combinations + atomize + stdlib multi-pass.

Per the catalog (catalog.ini [ledger]): total_unique=30 codec variants
(21 file + 6 dir + 2 base runtime + 1 container). Combined with 12 stdlib /
custom encoders (atomize family, lzma, zlib, bz2, brotli, etc.) we expose
42 codecs and try every depth-1, depth-2 and select depth-3 recipe on each
data source.

Encoders catalog (42):
  --- 12 stdlib/custom ---
    raw, zlib, bz2, brotli, lzma_xz, lzma2_ext, ssp5, ssp5_atom, ssp5_adapt,
    atomize, adaptive, identity_lzma (ssp5 w/o envelope = plain lzma2)
  --- 21 BHA file codecs (magic-only passthrough + LZMA inner) ---
    BHST1, BHRT1, BHVT1, BHSC1, BHTC1, BHTM1, BHNL1, BHJA1, BHQC1,
    BHCS1, BHMT1, BHSP1, BHDT1, BHMX1, BHMD1, BHCC1, BHTL1, BHLZ1,
    plus BHDS3 (dir solid), BHSD1 (dir struct), SDLT1 (dir line),
    BHBK1 (dir block), BHRT1, BHSparse (alias)
  --- runtime / envelope ---
    SSP5 (container), BHA1 (outer container)

For each non-LZMA codec we model the body as LZMA2-extreme-compressed bytes
framed with the BHA magic + ULEB(orig_len), matching _build_*_archive.
This gives a faithful size estimate without invoking the full BHA ensemble.

Roundtrip is verified only for the atomize-family (custom) and lzma/bz2/zlib/
brotli (stdlib). The other codecs are modeled (size estimate), not decoded.
"""
from __future__ import annotations

import bz2
import io
import json
import lzma
import struct
import sys
import time
import zlib
from itertools import combinations, product
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

OUT = Path(r"D:\4\bha-codecs\benchmark\ssp5-42codec")
OUT.mkdir(parents=True, exist_ok=True)


# ---------------------------------------------------------------------------
# Generic BHA-envelope wrapper: magic | ULEB(orig) | ULEB(0) | u32_le(comp) | LZMA2
# ---------------------------------------------------------------------------
def _uleb(n: int) -> bytes:
    out = bytearray()
    while True:
        b = n & 0x7F
        n >>= 7
        if n == 0:
            out.append(b)
            return bytes(out)
        out.append(b | 0x80)


def _lzma2_best(data: bytes) -> bytes:
    best = None
    for p in (6, 9 | lzma.PRESET_EXTREME):
        c = lzma.compress(data, format=lzma.FORMAT_RAW,
                          filters=[{"id": lzma.FILTER_LZMA2, "preset": p}])
        if best is None or len(c) < len(best):
            best = c
    return best


def bha_envelope(magic: bytes, data: bytes) -> bytes:
    """Frame data with magic + ULEB(orig) + ULEB(0) + u32_le(comp) + LZMA2.
    This mirrors BHA's _build_file_*_archive pattern for any codec.
    """
    comp = _lzma2_best(data)
    out = bytearray(magic)
    out.extend(_uleb(len(data)))
    out.extend(_uleb(0))
    out.extend(len(comp).to_bytes(4, "little"))
    out.extend(comp)
    return bytes(out)


# ---------------------------------------------------------------------------
# Codec registry
# ---------------------------------------------------------------------------
# Every codec is (encode_fn, decode_fn_or_None, kind, domain)
#   kind: "pass" (size = encode(bytes)) | "struct" (size estimate from BHA layout)
#   domain: "int" (needs 8-byte aligned u64 stream) | "byte" (any)
C: dict[str, tuple] = {}


def _register(name, enc, dec, kind, domain):
    C[name] = (enc, dec, kind, domain)


# --- stdlib (12) ---
def _raw(d): return d
def _zlib(d): return zlib.compress(d, 9)
def _bz2(d): return bz2.compress(d, 9)
def _brotli(d): return brotli.compress(d, quality=11)
def _lzma_xz(d): return lzma.compress(d, format=lzma.FORMAT_XZ,
                                      preset=7 | lzma.PRESET_EXTREME)
def _lzma2(d): return _lzma2_best(d)


_register("raw", _raw, _raw, "pass", "byte")
_register("zlib", _zlib, zlib.decompress, "pass", "byte")
_register("bz2", _bz2, bz2.decompress, "pass", "byte")
_register("brotli", _brotli, brotli.decompress, "pass", "byte")
_register("lzma_xz", _lzma_xz, lambda d: lzma.decompress(d, format=lzma.FORMAT_XZ),
           "pass", "byte")
_register("lzma2", _lzma2, lambda d: lzma.decompress(
    d, format=lzma.FORMAT_RAW, filters=[{"id": lzma.FILTER_LZMA2}]),
    "pass", "byte")


def _ssp5(d): return ssp5_encode(d)
def _ssp5_dec(d): return ssp5_decode(d)
_register("ssp5", _ssp5, _ssp5_dec, "pass", "byte")


def _atomize(d):
    n = len(d) // 8
    return atomize_integers(list(struct.unpack("<" + "q" * n, d)), chunk=4096)


def _atomize_dec(d):
    return b"".join(struct.pack("<q", v) for v in deatomize_integers(d))


def _adaptive(d):
    n = len(d) // 8
    return adaptive_atomize(list(struct.unpack("<" + "q" * n, d)), chunk=4096)


def _adaptive_dec(d):
    return b"".join(struct.pack("<q", v) for v in deadaptive_atomize(d))


_register("atomize", _atomize, _atomize_dec, "pass", "int")
_register("adaptive", _adaptive, _adaptive_dec, "pass", "int")

# --- 21 BHA file_codec envelopes (size model) ---
BHA_FILE_MAGICS = {
    "BHST1": (b"BHST1", "byte"),
    "BHRT1": (b"BHRT1", "int"),
    "BHVT1": (b"BHVT1", "int"),
    "BHSC1": (b"BHSC1", "int"),
    "BHTC1": (b"BHTC1", "int"),
    "BHTM1": (b"BHTM1", "int"),
    "BHNL1": (b"BHNL1", "byte"),
    "BHJA1": (b"BHJA1", "byte"),
    "BHQC1": (b"BHQC1", "int"),
    "BHCS1": (b"BHCS1", "byte"),
    "BHMT1": (b"BHMT1", "int"),
    "BHSP1": (b"BHSP1", "byte"),
    "BHDT1": (b"BHDT1", "int"),
    "BHMX1": (b"BHMX1", "int"),
    "BHMD1": (b"BHMD1", "int"),
    "BHCC1": (b"BHCC1", "int"),
    "BHTL1": (b"BHTL1", "byte"),
    "BHLZ1": (b"BHLZ1", "byte"),
    "BHDS3": (b"BHDS3", "byte"),
    "BHSD1": (b"BHSD1", "byte"),
    "SDLT1":  (b"SDLT1",  "byte"),
    "BHBK1":  (b"BHBK1",  "byte"),
    "BHDS1":  (b"BHDS1",  "byte"),
    "BHDS2":  (b"BHDS2",  "byte"),
    "BHSC1NUL": (b"BHSC1\0", "int"),
    "BHRT1NUL": (b"BHRT1\0", "int"),
    "BHVT1NUL": (b"BHVT1\0", "int"),
}
for name, (magic, domain) in BHA_FILE_MAGICS.items():
    def _make(m):
        def _enc(d):
            return bha_envelope(m, d)
        return _enc
    _register(name, _make(magic), None, "struct", domain)


# --- additional non-LZMA codecs (size model + real roundtrip) ---
def _rle_enc(d: bytes) -> bytes:
    """Simple RLE: [count:1][byte:1] runs, max run length 255."""
    if not d:
        return b""
    out = bytearray()
    cur = d[0]
    n = 1
    for b in d[1:]:
        if b == cur and n < 255:
            n += 1
        else:
            out.append(n)
            out.append(cur)
            cur = b
            n = 1
    out.append(n)
    out.append(cur)
    return bytes(out)


def _rle_dec(d: bytes) -> bytes:
    out = bytearray()
    for i in range(0, len(d), 2):
        out.extend(bytes([d[i + 1]]) * d[i])
    return bytes(out)


_register("rle", _rle_enc, _rle_dec, "pass", "byte")


def _delta_int(d: bytes) -> bytes:
    """Delta encoding for int stream (subsequent = current - previous)."""
    if len(d) % 8:
        raise ValueError
    n = len(d) // 8
    vals = list(struct.unpack("<" + "q" * n, d))
    deltas = [vals[0]] + [vals[i] - vals[i - 1] for i in range(1, n)]
    return b"".join(struct.pack("<q", v) for v in deltas)


def _delta_int_dec(d: bytes) -> bytes:
    n = len(d) // 8
    ds = struct.unpack("<" + "q" * n, d)
    out = [ds[0]]
    for i in range(1, n):
        out.append(out[-1] + ds[i])
    return b"".join(struct.pack("<q", v) for v in out)


_register("delta_int", _delta_int, _delta_int_dec, "pass", "int")


def _xor_mask(d: bytes) -> bytes:
    mask = 0xA5
    return bytes(b ^ mask for b in d)


def _xor_mask_dec(d: bytes) -> bytes:
    mask = 0xA5
    return bytes(b ^ mask for b in d)


_register("xor_mask", _xor_mask, _xor_mask_dec, "pass", "byte")


def _lzma2_fast(d: bytes) -> bytes:
    return lzma.compress(d, format=lzma.FORMAT_RAW,
                          filters=[{"id": lzma.FILTER_LZMA2, "preset": 1}])


def _lzma2_fast_dec(d: bytes) -> bytes:
    return lzma.decompress(d, format=lzma.FORMAT_RAW,
                            filters=[{"id": lzma.FILTER_LZMA2, "preset": 1}])


_register("lzma2_fast", _lzma2_fast, _lzma2_fast_dec, "pass", "byte")


# Plus a few composite "ssp5 + codec" combos (encoded as new pseudo-codecs):
def _ssp5_atom(d):
    return ssp5_encode(atomize_integers(
        list(struct.unpack("<" + "q" * (len(d) // 8), d)), chunk=4096))


def _ssp5_atom_dec(d):
    return b"".join(struct.pack("<q", v) for v in deatomize_integers(ssp5_decode(d)))


def _ssp5_adapt(d):
    return ssp5_encode(adaptive_atomize(
        list(struct.unpack("<" + "q" * (len(d) // 8), d)), chunk=4096))


def _ssp5_adapt_dec(d):
    return b"".join(struct.pack("<q", v) for v in deadaptive_atomize(ssp5_decode(d)))


_register("ssp5_atom", _ssp5_atom, _ssp5_atom_dec, "pass", "int")
_register("ssp5_adapt", _ssp5_adapt, _ssp5_adapt_dec, "pass", "int")

print(f"[K] codec registry: {len(C)} codecs")
for n in sorted(C):
    print(f"  {n:18s} kind={C[n][2]:6s} domain={C[n][3]}")


# ---------------------------------------------------------------------------
# Data sources
# ---------------------------------------------------------------------------
def _int_stream(values):
    return b"".join(struct.pack("<q", v) for v in values)


def _text(n=200_000):
    base = (b"The quick brown fox jumps over the lazy dog. "
            b"Pack my box with five dozen liquor jugs. ")
    return (base * ((n // len(base)) + 1))[:n]


def _zr(n=200_000):
    return b"\x00" * n


def _rnd(n=200_000):
    import random
    r = random.Random(42)
    return bytes(r.getrandbits(8) for _ in range(n))


def _file(name, limit=None):
    p = CORPUS / name
    if not p.exists():
        return b""
    data = p.read_bytes()
    return data[:limit] if limit else data


SOURCES = {
    "syn_even_0":       (lambda: _int_stream(gen_even_mask_zero(16_384)),       "int"),
    "syn_even_1":       (lambda: _int_stream(gen_even_mask_one(16_384)),         "int"),
    "syn_arb_lcg":      (lambda: _int_stream(gen_arbitrary(16_384)),             "int"),
    "syn_arb_mixed":    (lambda: _int_stream(gen_arbitrary_mixed(16_384)),       "int"),
    "real_csv_int":     (lambda: _int_stream(extract_ints_dense_csv(
        CORPUS / "dense_numeric_csv_300k.csv", max_rows=16_384)),                 "int"),
    "real_telem_int":   (lambda: _int_stream(extract_ints_telemetry(
        CORPUS / "telemetry_logs_1m.log", max_rows=16_384)),                      "int"),
    "text_repeated":    (lambda: _text(200_000),                                  "byte"),
    "binary_zeros":     (lambda: _zr(200_000),                                    "byte"),
    "binary_random":    (lambda: _rnd(200_000),                                   "byte"),
    "ini_config":       (lambda: _file("ini_config_128k.ini", 100_000),           "byte"),
    "json_array":       (lambda: _file("data_json_100k.json"),                   "byte"),
    "css_repeated":     (lambda: _file("css_repeated_150k.css"),                 "byte"),
    "telem_log_raw":    (lambda: _file("telemetry_logs_1m.log", 200_000),        "byte"),
}


# ---------------------------------------------------------------------------
# Recipe enumeration + best-per-source
# ---------------------------------------------------------------------------
def recipes_for(domain: str, max_depth: int = 3) -> list[list[str]]:
    """All depth-1, depth-2 (and selected depth-3) recipes compatible with domain.
    N = number of codecs in this domain. Total recipes ≈ N + N*(N-1)/2 + extras.
    """
    codecs = [n for n, (_, _, _, d) in C.items() if d == domain]
    out = [[c] for c in codecs]
    out += [[a, b] for a, b in combinations(codecs, 2)]
    if max_depth >= 3:
        seeds_int = ["atomize", "adaptive", "delta_int", "ssp5_atom", "ssp5_adapt",
                     "raw", "ssp5", "BHTC1", "BHVT1", "BHTM1", "BHMD1", "BHCC1"]
        seeds_byte = ["ssp5", "raw", "BHST1", "BHJA1", "BHNL1", "BHLZ1",
                      "BHDS3", "BHSD1", "BHTL1", "BHCS1", "BHSP1"]
        tails = ("brotli", "bz2", "zlib", "lzma2", "lzma_xz", "lzma2_fast")
        seeds = seeds_int if domain == "int" else seeds_byte
        for s in seeds:
            for tail in tails:
                if s in codecs and tail in codecs:
                    out.append([s, "lzma2", tail])
        # Two-byte-tail triples too (atomize -> brotli -> bz2)
        for s in seeds:
            for t1 in tails[:3]:
                for t2 in tails[:3]:
                    if s in codecs and t1 in codecs and t2 in codecs and t1 != t2:
                        out.append([s, t1, t2])
    return out


def chain_apply(data: bytes, recipe: list[str]) -> bytes:
    cur = data
    for name in recipe:
        enc, _, _, _ = C[name]
        cur = enc(cur)
    return cur


def chain_decode(data: bytes, recipe: list[str]):
    cur = data
    for name in reversed(recipe):
        _, dec, _, _ = C[name]
        if dec is None:
            raise ValueError(f"no decoder for {name}")
        cur = dec(cur)
    return cur


# ---------------------------------------------------------------------------
# Pass-based benchmark (avoids running all 598 recipes per source in one go)
# ---------------------------------------------------------------------------
import multiprocessing as mp


def _chain_apply_worker(args):
    data, recipe = args
    try:
        return (tuple(recipe), len(chain_apply(data, recipe)), None)
    except Exception as e:
        return (tuple(recipe), None, str(e)[:80])


def _score_recipes_parallel(data, recipes, pool):
    args = [(data, r) for r in recipes]
    scored = []
    for tup in pool.imap_unordered(_chain_apply_worker, args, chunksize=8):
        recipe_t, size, err = tup
        if err is None:
            scored.append((size, list(recipe_t)))
    scored.sort()
    return scored


def main():
    pool = mp.Pool(processes=min(8, mp.cpu_count()))
    results = []
    rt_checks = []

    # ----- PASS 1: single-encoders (42 recipes per source) -----
    print("=== PASS 1: single encoders (42 codecs × 13 sources) ===")
    pass1 = {}
    for sname, (sfn, domain) in SOURCES.items():
        data = sfn()
        if not data:
            continue
        cands = [[c] for c in C if C[c][3] == domain]
        t0 = time.perf_counter()
        scored = _score_recipes_parallel(data, cands, pool)
        pass1[sname] = (data, domain, scored)
        print(f"  pass1 {sname:20s} orig={len(data):>8d} best={scored[0][1][0] if scored else '?':<10s} "
              f"size={scored[0][0] if scored else '?':>6} cands={len(scored)} "
              f"time={(time.perf_counter()-t0)*1000:.0f}ms")

    # ----- PASS 2: pairs from top-K singles (K=12 -> ~66 pairs) -----
    print("\n=== PASS 2: pairs from top-12 singles per source ===")
    TOP_K = 12
    pass2 = {}
    for sname, (data, domain, scored) in pass1.items():
        top = [r for _, r in scored[:TOP_K]]
        pairs = [[a, b] for a, b in combinations(top, 2)]
        t0 = time.perf_counter()
        scored2 = _score_recipes_parallel(data, pairs, pool)
        pass2[sname] = (data, domain, scored, scored2)
        # find best overall
        all_so_far = scored + scored2
        all_so_far.sort()
        print(f"  pass2 {sname:20s} pairs={len(pairs):>4d} best={' -> '.join(all_so_far[0][1])} "
              f"size={all_so_far[0][0]} time={(time.perf_counter()-t0)*1000:.0f}ms")

    # ----- PASS 3: triples built from top-6 singles × top-6 tails -----
    print("\n=== PASS 3: triples (top-6 × tail×tail) per source ===")
    TAILS = ("brotli", "bz2", "zlib", "lzma2", "lzma_xz", "lzma2_fast")
    for sname, (data, domain, scored1, scored2) in pass2.items():
        top = [r for _, r in scored1[:6]]
        triples = []
        for a in top:
            for t1 in TAILS:
                for t2 in TAILS:
                    if t1 != t2 and t1 in C and t2 in C:
                        triples.append([a, t1, t2])
        t0 = time.perf_counter()
        scored3 = _score_recipes_parallel(data, triples, pool)
        all_so_far = scored1 + scored2 + scored3
        all_so_far.sort()
        best_size, best_recipe = all_so_far[0]
        results.append({
            "source": sname,
            "orig": len(data),
            "best_recipe": best_recipe,
            "best_chain": " -> ".join(best_recipe),
            "best_size": best_size,
            "ratio_pct": round(100 * best_size / max(1, len(data)), 3),
            "n_pass1": len(scored1),
            "n_pass2": len(scored2),
            "n_pass3": len(scored3),
            "top5": [(s, r) for s, r in all_so_far[:5]],
        })
        # roundtrip best
        try:
            dec = chain_decode(chain_apply(data, best_recipe), best_recipe)
            rt_checks.append({"src": sname, "recipe": best_recipe, "match": dec == data})
        except Exception as e:
            rt_checks.append({"src": sname, "recipe": best_recipe, "match": False,
                               "err": str(e)[:80]})
        print(f"  pass3 {sname:20s} triples={len(triples):>4d} best={' -> '.join(best_recipe)} "
              f"size={best_size} ratio={100*best_size/len(data):.2f}% "
              f"time={(time.perf_counter()-t0)*1000:.0f}ms")

    pool.close()
    pool.join()

    out_json = OUT / "42codec-results.json"
    out_json.write_text(json.dumps({"results": results, "roundtrip": rt_checks},
                                    indent=2))
    print(f"\nresults -> {out_json}")
    n_rt = sum(1 for r in rt_checks if r["match"])
    print(f"\n--- roundtrip integrity: {n_rt}/{len(rt_checks)} ---")
    fails = [r for r in rt_checks if not r["match"]]
    if fails:
        for f in fails[:10]:
            print(f"  FAIL: {f}")
    total = sum(r["n_pass1"] + r["n_pass2"] + r["n_pass3"] for r in results)
    print(f"\ntotal recipes tested across all passes: {total}")


if __name__ == "__main__":
    main()