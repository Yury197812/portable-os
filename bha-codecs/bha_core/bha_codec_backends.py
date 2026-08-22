"""bha_codec_backends: thin wrappers around external codec libraries.

Brotli is exposed here as a single self-contained backend so the rest of
bha_core (gates, recommender, parallel orchestrator) can use it without
each module importing the third-party library directly.

Why a separate module:
  - Centralises the optional dependency (`brotli` may not be installed)
  - One place to add quality presets, version handling, fallback logic
  - Keeps `bha_parallel.worker_gate` lean (it dispatches by gate name)

Why brotli-q11 specifically:
  - `BHA_VS_BROTLI.md` shows brotli q11 wins by 28% size on <100KB web
    files vs BHA structural codecs.
  - Speed: 600x faster to pack than BHA on small inputs (skip ssp +
    transform retries).
  - Bit-exact round-trip via `brotli.compress`/`decompress` (no envelope,
    no ssp round-trip - the bare compressed blob is the archive).

Limitations:
  - Single-stream only. No multi-file archive support (use BHA envelope
    when that's needed).
  - Quality 11 is slow on large inputs (~10 MB/s); not recommended for
    files >256 KB. v11 routing caps brotli at <=64 KB to stay safe.
  - No LZMA2/brotli hybrid: brotli on already-LZMA data loses to BHA.
"""
from __future__ import annotations
from typing import Optional


# Lazy-import brotli so bha_core stays importable when brotli is missing.
_brotli = None
_brotli_import_error: Optional[Exception] = None


def _get_brotli():
    """Return the brotli module, loading it on first call.

    Returns None if brotli is not installed. Callers must check and skip
    the gate gracefully (same pattern as `_load_runtime()` in bha.py).
    """
    global _brotli, _brotli_import_error
    if _brotli is not None:
        return _brotli
    if _brotli_import_error is not None:
        return None
    try:
        import brotli  # type: ignore
        _brotli = brotli
        return brotli
    except Exception as e:  # ImportError, OSError, etc.
        _brotli_import_error = e
        return None


# Quality presets exposed to the rest of the stack. Keep names stable -
# the recommender and worker_gate dispatch by these strings.
BROTLI_QUALITY = {
    'brotli_q6': 6,   # faster, slightly worse ratio
    'brotli_q11': 11, # slower, best ratio (Brotli's canonical top-1)
}


def is_available() -> bool:
    """True if brotli Python binding is importable in this process."""
    return _get_brotli() is not None


def import_error() -> Optional[Exception]:
    """Return the import error if brotli is not available, else None."""
    if _brotli is not None:
        return None
    # Trigger lazy import attempt if not yet tried
    if _brotli_import_error is None:
        _get_brotli()
    return _brotli_import_error


def brotli_compress(data: bytes, quality: int = 11) -> bytes:
    """Compress data with brotli at given quality (0-11)."""
    br = _get_brotli()
    if br is None:
        raise RuntimeError("brotli not installed; gate disabled")
    return br.compress(data, quality=quality)


def brotli_decompress(data: bytes) -> bytes:
    """Decompress brotli-framed blob back to original bytes."""
    br = _get_brotli()
    if br is None:
        raise RuntimeError("brotli not installed; gate disabled")
    return br.decompress(data)


def quality_for(name: str) -> Optional[int]:
    """Return numeric quality for a gate name like 'brotli_q11', or None."""
    return BROTLI_QUALITY.get(name)


def list_gate_names() -> list[str]:
    """Return all brotli gate names this backend supports."""
    return list(BROTLI_QUALITY.keys())


# ---------------------------------------------------------------------------
# Sanity check / self-test
# ---------------------------------------------------------------------------
if __name__ == '__main__':
    if not is_available():
        print(f'brotli NOT available: {import_error()}')
        raise SystemExit(1)
    test_data = b'<html><body>Hello, brotli!</body></html>' * 10
    c = brotli_compress(test_data, quality=11)
    d = brotli_decompress(c)
    assert d == test_data, 'round-trip failed'
    print(f'brotli ok: {len(test_data)} -> {len(c)} ({len(c)/len(test_data):.1%})')
    for name, q in BROTLI_QUALITY.items():
        c = brotli_compress(test_data, quality=q)
        print(f'  {name}: q={q} -> {len(c)} bytes')