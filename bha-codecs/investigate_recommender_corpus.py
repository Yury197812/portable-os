"""Investigation N: end-to-end recommender pipeline on the full TEST corpus.

Validates the recommender (M) on all 50 files in
D:\\PROJECT UNIVERSE\\01Compression\\BHA\\TEST (out-of-sample from training).

For each file:
  1. Extract features (entropy, zero_ratio, ascii_ratio, etc.)
  2. Predict codec via recommend()
  3. Compress with the predicted codec
  4. Compress with real BHA (_compress_best)
  5. Compare sizes

Outputs per-file CSV + summary report (accuracy, total compression ratio,
ours vs BHA, cases where ours beats BHA, etc.)
"""
from __future__ import annotations

import json
import os
import struct
import sys
import time
import warnings
from pathlib import Path

warnings.filterwarnings("ignore")

BHA_DIR = Path(r"D:\PROJECT UNIVERSE\01Compression\BHA")
sys.path.insert(0, str(BHA_DIR))
import black_hole_archiver as bha  # noqa: E402

sys.path.insert(0, r"D:\4\bha-codecs")
from investigate_ssp5_recommender import features_from_path, recommend  # noqa: E402
from investigate_ssp5_even_atom import ssp5_encode, ssp5_decode  # noqa: E402
from investigate_ssp5_adaptive import adaptive_atomize, deadaptive_atomize  # noqa: E402

import lzma
import brotli
import bz2
import zlib

OUT = Path(r"D:\4\bha-codecs\benchmark\recommender-corpus")
OUT.mkdir(parents=True, exist_ok=True)
CORPUS = Path(r"D:\PROJECT UNIVERSE\01Compression\BHA\TEST")


# ---------------------------------------------------------------------------
# Codec dispatch
# ---------------------------------------------------------------------------
def _brotli_enc(d): return brotli.compress(d, quality=11)
def _bz2_enc(d): return bz2.compress(d, 9)
def _zlib_enc(d): return zlib.compress(d, 9)
def _lzma2_enc(d):
    best = None
    for p in (6, 9 | lzma.PRESET_EXTREME):
        c = lzma.compress(d, format=lzma.FORMAT_RAW,
                          filters=[{"id": lzma.FILTER_LZMA2, "preset": p}])
        if best is None or len(c) < len(best):
            best = c
    return best


def _raw_enc(d): return d


def _ours_adaptive_atomize_enc(d: bytes) -> bytes:
    """Our adaptive atomize -> SSP5 envelope. Works for any 8-byte aligned data."""
    if len(d) % 8 == 0 and len(d) > 0:
        try:
            n = len(d) // 8
            vals = list(struct.unpack("<" + "q" * n, d))
            adapt = adaptive_atomize(vals, chunk=4096)
            return ssp5_encode(adapt)
        except Exception:
            pass
    return ssp5_encode(d)


def _ssp5_enc(d): return ssp5_encode(d)


CODECS = {
    "raw": _raw_enc,
    "brotli": _brotli_enc,
    "bz2": _bz2_enc,
    "zlib": _zlib_enc,
    "lzma2": _lzma2_enc,
    "SSP5": _ssp5_enc,
    "ours_adaptive_atomize": _ours_adaptive_atomize_enc,
}


# BHA structural codecs require running _compress_best which we already do
# via real_bha. For prediction purposes we map them to SSP5 fallback (size
# model) so the pipeline can run end-to-end without the heavy BHA encoder.


# ---------------------------------------------------------------------------
# Run
# ---------------------------------------------------------------------------
def main():
    # Try to load BHA runtime once
    try:
        bha._load_runtime()
        bha_ok = True
        print("[N] BHA runtime loaded OK")
    except Exception as e:
        bha_ok = False
        print(f"[N] BHA runtime FAILED: {e}")

    manifest_path = CORPUS / "manifest.json"
    manifest = json.loads(manifest_path.read_text())
    files = manifest["files"]
    print(f"[N] {len(files)} files in manifest")

    rows = []
    summary = {"ours_wins": 0, "bha_wins": 0, "ties": 0, "skipped": 0}
    total_orig = 0
    total_ours = 0
    total_bha = 0

    for f in files:
        fname = f["name"]
        path = CORPUS / fname
        if not path.exists():
            summary["skipped"] += 1
            continue
        data = path.read_bytes()
        orig = len(data)
        total_orig += orig

        # 1) predict
        feats = features_from_path(path)
        codec, reason = recommend(feats)

        # 2) compress with predicted codec
        if codec in CODECS:
            try:
                ours_bytes = CODECS[codec](data)
                ours_size = len(ours_bytes)
                ours_ok = True
            except Exception as e:
                ours_size = None
                ours_ok = False
                ours_err = str(e)[:80]
        elif codec.startswith("BH"):  # BHA structural — fall back to SSP5 size model
            ours_bytes = ssp5_encode(data)
            ours_size = len(ours_bytes)
            ours_ok = True
            codec_used = f"{codec}(via SSP5)"
        else:
            ours_size = None
            ours_ok = False
            codec_used = codec
        if ours_ok:
            total_ours += ours_size

        # 3) compress with real BHA
        if bha_ok:
            t0 = time.perf_counter()
            try:
                bha_archive, _ = bha._compress_best(data, path)
                bha_size = len(bha_archive)
                bha_ms = (time.perf_counter() - t0) * 1000
                bha_magic = bha_archive[:5].split(b"\x00", 1)[0].decode("ascii", errors="replace")
            except Exception as e:
                bha_size = None
                bha_ms = None
                bha_magic = f"err:{str(e)[:40]}"
        else:
            bha_size = None
            bha_ms = None
            bha_magic = None
        if bha_size is not None:
            total_bha += bha_size

        # 4) winner
        winner = None
        if ours_ok and bha_size is not None:
            if ours_size < bha_size:
                winner = "ours"
                summary["ours_wins"] += 1
            elif bha_size < ours_size:
                winner = "bha"
                summary["bha_wins"] += 1
            else:
                winner = "tie"
                summary["ties"] += 1

        rows.append({
            "file": fname,
            "domain": f.get("domain"),
            "orig": orig,
            "predicted_codec": codec,
            "reason": reason,
            "ours_size": ours_size,
            "ours_pct": round(100 * ours_size / orig, 2) if ours_ok else None,
            "bha_size": bha_size,
            "bha_pct": round(100 * bha_size / orig, 2) if bha_size else None,
            "bha_magic": bha_magic,
            "bha_ms": round(bha_ms, 1) if bha_ms else None,
            "winner": winner,
            "features": feats,
        })
        status = winner or "?"
        print(f"  {fname:42s} pred={codec:22s} ours={rows[-1]['ours_pct']}% "
              f"bha={rows[-1]['bha_pct']}%  winner={status}")

    out_json = OUT / "corpus-results.json"
    out_json.write_text(json.dumps({
        "summary": {
            **summary,
            "n_files": len(rows),
            "total_orig": total_orig,
            "total_ours": total_ours,
            "total_bha": total_bha,
            "ours_total_pct": round(100 * total_ours / max(1, total_orig), 2),
            "bha_total_pct": round(100 * total_bha / max(1, total_orig), 2),
        },
        "rows": rows,
    }, indent=2))
    print(f"\nresults -> {out_json}")
    print(f"\n--- summary ---")
    print(f"  files tested: {len(rows)}")
    print(f"  ours wins: {summary['ours_wins']}")
    print(f"  BHA wins: {summary['bha_wins']}")
    print(f"  ties: {summary['ties']}")
    print(f"  total orig:  {total_orig:>10,} bytes")
    print(f"  total ours:  {total_ours:>10,} bytes ({100 * total_ours / max(1, total_orig):.2f}%)")
    print(f"  total BHA:   {total_bha:>10,} bytes ({100 * total_bha / max(1, total_orig):.2f}%)")


if __name__ == "__main__":
    main()