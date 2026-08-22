"""bha_recommender_v11: production recommender for bha_parallel.

Trained on telemetry_v1.json (598 points, 50 files × 13 codecs). Replaces
the static v9b k-NN recommender with telemetry-driven per-extension
priorities. Provides two APIs:

  recommend(name, size, k=3)
    Returns top-K BHA gate names likely to win. Order = priority for
    bha_parallel: run highest-priority first, then descending.

  lzma_preset_for(name, size)
    Returns 6 or 9 — which LZMA preset the lzma_fallback gate should use.
    v11 telemetry says: lzma6 wins on text (HTML/CSS/JSON), lzma9_extreme
    wins on smaller files where extra time is justified.

Files:
  - `recommender_v11_rules.json` produced by recommender_v11.py training
  - rules loaded via _load_rules() at import (cached)

Fallback when telemetry is sparse: use a global "always-likely" priority
list (delta_pp, lzma_fallback, then known CSV/JSON gates).

Why we don't gate by codec name (e.g. brotli_pp) but by LZMA preset:
  - BHA orchestrator has no `brotli_pp` or `zstd_pp` gate; only the
    fallback gate uses LZMA. So v11's most impactful control is which
    preset the fallback picks.
  - For per-codec parity with telemetry, we'd need to add brotli/zstd
    gates. That's a separate (larger) refactor.
"""
from __future__ import annotations
import json
import math
import statistics
from collections import defaultdict
from functools import lru_cache
from pathlib import Path

# Rules JSON sits next to this module. The training script
# (recommender_v11.py) writes rules.json alongside it.
_HERE = Path(__file__).parent
RULES_PATH = _HERE / 'rules.json'


# ---------------------------------------------------------------------------
# Per-extension gate priority (built from telemetry)
# ---------------------------------------------------------------------------
DEFAULT_PRIORITY = [
    'delta_pp',
    'lzma_fallback',
    'quoted_csv', 'telemetry_csv', 'json_array', 'tabular_col',
    'sparse_pattern', 'sparse_col', 'mixed_formula',
    'record_transpose', 'vartrans', 'line_norm',
    'markdown_table', 'css_struct', 'dense_sparse',
    'pp_dedup_substring', 'pp_bcj_x86',
]


# Telemetry-driven per-extension priority: put "likely best" gate first.
# These match the per-extension best codec from telemetry_v1:
#   .html, .css, .ini, .xml, .jsonl, .md, .raw, .toml, .yaml → lzma6 wins
#   .csv, .zip, .semicolon → brotli_11 wins (mapped to lzma_fallback here)
#   .bin, .log → lzma9_extreme wins on some, brotli_11 on others
EXT_PRIORITY = {
    'html':     ['lzma_fallback', 'delta_pp', 'css_struct', 'pp_dedup_substring'],
    'css':      ['lzma_fallback', 'delta_pp', 'css_struct'],
    'ini':      ['lzma_fallback', 'delta_pp', 'pp_dedup_substring'],
    'toml':     ['lzma_fallback', 'delta_pp', 'pp_dedup_substring'],
    'xml':      ['lzma_fallback', 'delta_pp', 'pp_dedup_substring'],
    'jsonl':    ['lzma_fallback', 'delta_pp'],
    'md':       ['lzma_fallback', 'markdown_table', 'delta_pp'],
    'raw':      ['lzma_fallback', 'delta_pp'],
    'yaml':     ['lzma_fallback', 'delta_pp'],
    'json':     ['lzma_fallback', 'json_array', 'delta_pp'],
    'csv':      ['delta_pp', 'lzma_fallback', 'telemetry_csv', 'quoted_csv',
                 'tabular_col', 'record_transpose'],
    'tsv':      ['delta_pp', 'lzma_fallback', 'quoted_csv', 'record_transpose'],
    'txt':      ['lzma_fallback', 'line_norm', 'delta_pp', 'pp_dedup_substring'],
    'log':      ['lzma_fallback', 'sparse_pattern', 'line_norm', 'delta_pp'],
    'zip':      ['lzma_fallback', 'delta_pp', 'pp_bcj_x86'],
    'js':       ['lzma_fallback', 'delta_pp', 'pp_dedup_substring'],
    'bin':      ['lzma_fallback', 'pp_bcj_x86'],
}


# Per-extension LZMA preset override (tiny size bucket handled separately
# in lzma_preset_for, not via this dict).
EXT_LZMA_PRESET = {
    'html': 6, 'css': 6, 'ini': 6, 'toml': 6, 'xml': 6, 'jsonl': 6, 'md': 6,
    'raw': 6, 'yaml': 6, 'json': 6, 'csv': 6, 'tsv': 6, 'txt': 6, 'log': 6,
    'zip': 6, 'js': 6, 'bin': 6,
}


# ---------------------------------------------------------------------------
# Brotli routing (T1: small-file web crossover fix)
# ---------------------------------------------------------------------------
# Reference: BHA_VS_BROTLI.md + telemetry_v2.json show brotli wins on
# web/structured-text content up to ~256 KB (crossover_html_400kb and
# bro_markdown-80k both go to brotli_11/brotli_6 in v2 telemetry).
# 256 KB = 2^18 is the new power-of-2 threshold; we stay conservative
# below 1 MB where BHA structural codecs start to dominate again.
BROTLI_SMALL_MAX = 1 << 18  # 256 KiB (was 64 KiB in T1; raised by T2 telemetry)

# Extensions where brotli wins for small inputs (from telemetry +
# BHA_VS_BROTLI cross-bucket 50k/80k benchmarks).
BROTLI_PREFERRED_EXTS = frozenset({
    'html', 'htm', 'css', 'json', 'md', 'markdown',
    'xml', 'ini', 'toml', 'yaml', 'yml', 'jsonl',
    'txt', 'svg', 'js', 'ts',
})

# Brotli priority extension to prepend for small files. Order matters:
# v11 picks highest-priority first, so brotli_q11 must come before
# brotli_q6 before BHA gates.
BROTLI_SMALL_PRIORITY = ['brotli_q11', 'brotli_q6']


# Codec name aliases (T2). The bench harness (bench_codecs.py) emits
# codec names from the stdlib/external registry: 'brotli_11', 'brotli_6'.
# The gate layer (bha_parallel.worker_gate, bha_codec_backends) uses
# 'brotli_q11' / 'brotli_q6' to match the bha_gates naming convention
# (`<codec>_<quality>`-style). They denote the SAME operation
# (brotli with quality=N); we translate telemetry names to gate names
# so the L8 recommender can dispatch a real BHA gate.
CODEC_ALIASES = {
    'brotli_11': 'brotli_q11',
    'brotli_6':  'brotli_q6',
}


def _alias_gate(name: str) -> str:
    """Translate telemetry codec name to bha gate name (or pass through)."""
    return CODEC_ALIASES.get(name, name)


@lru_cache(maxsize=1)
def _load_rules() -> dict:
    if not RULES_PATH.exists():
        return {}
    return json.loads(RULES_PATH.read_text())


def _features(name: str, size: int) -> dict:
    ext = Path(name).suffix.lower().lstrip('.') or 'none'
    # Size buckets (power-of-2 thresholds): tiny <8KiB, small <80KiB,
    # medium <400KiB, large <2MiB, xlarge >=2MiB. Bucket boundaries are
    # quantised to powers of 2 to keep the comparison branch-free
    # and to align with hardware cache boundaries.
    if size < (1 << 13):  # 8 KiB
        bucket = 'tiny'
    elif size < (1 << 16) | (1 << 14):  # 80 KiB = 64K + 16K
        bucket = 'small'
    elif size < (1 << 18) | (1 << 17):  # 400 KiB = 256K + 128K
        bucket = 'medium'
    elif size < (1 << 21):  # 2 MiB
        bucket = 'large'
    else:
        bucket = 'xlarge'
    return {'ext': ext, 'size_bucket': bucket, 'size_log': round(math.log2(max(size, 1)), 1)}


def _top_codec_for(name: str, size: int) -> tuple[str, str]:
    """Return (best_codec, source) where source is 'extension', 'global', or 'fallback'.

    Used internally to derive LZMA preset and gate priority. The returned
    codec name is aliased via CODEC_ALIASES so telemetry names like
    'brotli_11' become the gate name 'brotli_q11'.
    """
    rules = _load_rules()
    ext = _features(name, size)['ext']
    # Best per extension
    by_ext_rules = rules.get('rules_by_ext', {}).get(ext)
    if by_ext_rules and by_ext_rules.get('_count', 0) >= 2:
        counts = {k: v for k, v in by_ext_rules.items() if k != '_count'}
        best = max(counts, key=counts.get)
        return (_alias_gate(best), 'extension')
    # Best global
    dist = rules.get('codec_distribution', {})
    if dist:
        best = max(dist, key=dist.get)
        return (_alias_gate(best), 'global')
    return ('lzma6', 'fallback')


def lzma_preset_for(name: str, size: int) -> int:
    """Return LZMA preset (6 or 9) for this file's lzma_fallback gate."""
    feats = _features(name, size)
    # Tiny files (<8KiB) get EXTREME — small input means small
    # dictionary, so the time cost of EXTREME is amortized over the
    # small output.
    if feats['size_bucket'] == 'tiny':
        return 9
    codec, _ = _top_codec_for(name, size)
    # Map top codec to preset
    if codec == 'lzma9_extreme':
        return 9
    if codec in ('brotli_q11', 'brotli_q6', 'brotli_11', 'brotli_6', 'zstd_22'):
        return 9  # high-compression regimes benefit from EXTREME
    return 6  # default


def recommend(name: str, size: int, k: int = 5) -> list[str]:
    """Return prioritized list of BHA gate names for this file.

    Order matters: bha_parallel should run highest-priority gates first
    (so if pool has limited slots, the most likely winner is tried).

    The returned list is always of length >=k; falls back to
    DEFAULT_PRIORITY if extension is unknown.

    Brotli crossover (T1/T2): for web/structured-text extensions and
    small inputs (<=256 KB after T2 telemetry retraining), brotli_q11
    is prepended at index 0, since telemetry_v2 + BHA_VS_BROTLI
    baseline show it wins on this domain. Above the threshold, BHA
    structural codecs resume priority; brotli still appears later as
    a candidate.

    All gate names pass through _alias_gate() so that telemetry names
    like 'brotli_11' (from bench_codecs.py) are translated to the gate
    name 'brotli_q11' (from worker_gate / bha_codec_backends).
    """
    feats = _features(name, size)
    ext = feats['ext']
    priority = [_alias_gate(g) for g in EXT_PRIORITY.get(ext, DEFAULT_PRIORITY)]
    # Brotli crossover: prepend for small web files
    if ext in BROTLI_PREFERRED_EXTS and size <= BROTLI_SMALL_MAX:
        priority = BROTLI_SMALL_PRIORITY + [
            g for g in priority if g not in BROTLI_SMALL_PRIORITY
        ]
    # Pad to k if extension-specific list is too short
    if len(priority) < k:
        for g in DEFAULT_PRIORITY:
            g_aliased = _alias_gate(g)
            if g_aliased not in priority:
                priority.append(g_aliased)
            if len(priority) >= k:
                break
    return priority[:k]


def stats() -> dict:
    """Return recommender metrics from training."""
    rules = _load_rules()
    return {
        'version': rules.get('version'),
        'loo_top1_pct': rules.get('loo_metrics', {}).get('top1_pct'),
        'loo_top3_pct': rules.get('loo_metrics', {}).get('top3_pct'),
        'n_files': rules.get('loo_metrics', {}).get('n'),
        'codec_distribution': rules.get('codec_distribution'),
    }


# ---------------------------------------------------------------------------
# Tests
# ---------------------------------------------------------------------------
if __name__ == '__main__':
    print(f'recommender stats: {stats()}')
    print(f'\nRecommendation + LZMA preset examples:')
    test_files = [
        ('foo.html', 200_000),
        ('bar.csv', 500_000),
        ('baz.bin', 100_000),
        ('config.ini', 1_000),
        ('data.jsonl', 200_000),
        ('unknown.xyz', 50_000),
        ('tiny.txt', 500),
    ]
    for name, size in test_files:
        recs = recommend(name, size, k=5)
        preset = lzma_preset_for(name, size)
        print(f'  {name:25s}  size={size:>8d}  preset=lzma{preset}  gates={recs}')