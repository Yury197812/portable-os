# bha_core — Adaptive Multi-Codec Compression Pipeline

A telemetry-driven compression pipeline for the Black Hole Archiver (BHA)
codec stack. Picks the best codec per file using a v11 recommender
trained on real compression telemetry.

**Performance on 50 real BHA files:**

| Pipeline | Avg ratio | Avg bits/byte | Notes |
|----------|-----------|---------------|-------|
| `lzma_extreme` (preset 9) | 2.55× | 3.14 | Slowest, best raw |
| `lzma6` (preset 6) | 2.51× | 3.19 | Default; 6× faster than extreme |
| **`brotli_11`** | **2.51×** | **3.19** | Google web codec, fast |
| `zstd_22` | 2.41× | 3.32 | Facebook codec |
| `bz2_9` | 1.95× | 4.10 | Best on numeric CSV |
| `lz4` | 1.45× | 5.52 | Fastest, worst ratio |
| `snappy` | 1.40× | 5.72 | Fastest |

**v11 recommender:** 48.5% top-1 accuracy (vs v9b 42.0%) on 50-file BHA corpus.
**Persistent pool:** 2.14× avg speedup over per-call ProcessPoolExecutor.

---

## Install

```bash
pip install bha-core
# or with optional codecs:
pip install "bha-core[codecs]"
```

See **`INSTALL.md`** for full setup including BHA runtime integration.

---

## Quick start

### 1. Sequential compression (with wall-clock guard)

```python
from pathlib import Path
from bha_core import bha

data = Path("report.csv").read_bytes()
arc, stats, meta = bha.bha_compress(
    data,
    src_path=Path("report.csv"),
    total_timeout_s=20,
)
print(f"compressed: {len(arc)} bytes (ratio {100 * len(arc) / len(data):.2f}%)")
print(f"meta: {meta}")
# {'elapsed_s': 0.35, 'timed_out': False, 'reached_finish': True, ...}
```

### 2. Parallel compression with v11 recommender

```python
from pathlib import Path
from bha_core import bha_parallel

data = Path("big.log").read_bytes()
arc, meta = bha_parallel.bha_parallel_compress(data, src_path=Path("big.log"))
print(f"best gate: {meta['best_gate']}")
print(f"v11 priority: {meta.get('v11_priority')}")
print(f"v11 LZMA preset: {meta.get('v11_lzma_preset')}")
# best gate: pp_bcj_x86
# v11 priority: ['lzma_fallback', 'sparse_pattern', 'line_norm', 'delta_pp', 'quoted_csv']
# v11 LZMA preset: 9
```

### 3. Standalone v11 recommender API (no BHA runtime needed)

```python
from bha_core import bha_recommender_v11

# Gate recommendations
gates = bha_recommender_v11.recommend("data.csv", 500_000, k=5)
# ['delta_pp', 'lzma_fallback', 'telemetry_csv', 'quoted_csv', 'tabular_col']

# LZMA preset for the lzma_fallback gate
preset = bha_recommender_v11.lzma_preset_for("data.csv", 500_000)
# 6

# Stats from training
stats = bha_recommender_v11.stats()
# {'version': 'v11', 'loo_top1_pct': 48.5, 'loo_top3_pct': 76.8, ...}
```

### 4. Round-trip safe preprocessors

```python
from bha_core import bha_v10_pp_safe

# Find longest repeated substring, replace with back-ref token
data = b"hello world " * 100
pre, side = bha_v10_pp_safe.pp_dedup_substring_safe(data)
decoded = bha_v10_pp_safe.decode_dedup_substring(pre, side)
assert decoded == data  # round-trip safe

# x86 BCJ filter: zero out CALL/JMP offsets
x86_data = bytes([0xE8, 0x10, 0x00, 0x00, 0x00, 0xE9, 0x20, 0x00, 0x00, 0x00]) * 50
pre, side = bha_v10_pp_safe.pp_bcj_x86_safe(x86_data)
decoded = bha_v10_pp_safe.decode_bcj_x86(pre, side)
assert decoded == x86_data
```

### 5. Adaptive integer encoder

```python
from bha_core import bha_delta

# Adaptive int encoder picks the smallest of 3 modes:
#   0 = plain delta, 2 = delta-of-delta, 3/4 = XOR-i32/i64
vals = [i * i for i in range(1000)]  # quadratic series
enc = bha_delta._adaptive_encode_int(vals)
# enc[0] == 2 — dod wins for quadratic
dec = bha_delta._decode_adaptive(enc)
assert dec == vals
```

### 6. CLI tools (after `pip install bha-core`)

```bash
# Single-file packer with wall-clock guard
bha-pack myfile.csv

# Parallel orchestrator (uses v11 recommender by default)
bha-orchestrate data.csv log.txt archive.html
```

---

## Architecture overview

The package implements a 12-layer codec stack (L1-L12 from
`L1-L12-layers.md`). Each layer is independently testable.

```
L1 input → L2 sniffing → L3 preprocessor → L4 per-codec encoder
                                          ↓
L12 pipeline  ←  L11 CLI  ←  L10 container  ←  L9 parallel orchestrator
                              ↑
                          L8 v11 recommender  →  L7 envelope
```

| Layer | Module | Purpose |
|-------|--------|---------|
| L3 preprocessor | `bha_delta.py`, `bha_v10_pp_safe.py` | Restructure input to be more compressible |
| L6 entropy | (via BHA runtime LZMA2) | Statistical back-end |
| L8 recommender | `bha_recommender_v11.py`, `recommender_v11.py` | Pick best codec per file (48.5% top-1) |
| L9 orchestrator | `bha_parallel.py`, `bha_persistent_pool.py` | Run multiple gates concurrently |
| L11 CLI | `bha.py`, `bha_parallel._cli_orchestrator()` | User-facing interface |
| L12 pipeline | (orchestrator + CLI) | End-to-end compression |

For the full L1-L18 decomposition (including L13-L18 meta-layers),
see `L1-L12-layers.md`.

---

## What's inside

```
D:\4\bha-codecs\
├── bha_core/                  # Production package (8 modules + __init__)
│   ├── bha.py                  # Entry point with wall-clock guard
│   ├── bha_delta.py            # Adaptive int encoder
│   ├── bha_v10_pp_safe.py      # Round-trip safe preprocessors
│   ├── bha_parallel.py         # Parallel orchestrator (v11-integrated)
│   ├── bha_persistent_pool.py  # Singleton pool (2.14× speedup)
│   ├── bha_recommender_v11.py  # Production recommender API
│   ├── recommender_v11.py      # L15 training script
│   ├── bench_codecs.py         # 13-codec comparison harness
│   ├── catalog.ini             # BHA codec catalog (29 magics)
│   ├── rules.json              # v11 trained rules
│   ├── README.md               # Package docs
│   └── __init__.py             # Package marker
├── tests/                       # pytest suite (102 tests, 90 pass, 12 skip)
│   ├── conftest.py
│   ├── test_bha_recommender_v11.py  # 16 tests
│   ├── test_bha_v10_pp_safe.py      # 16 tests
│   ├── test_bha_delta.py            # 36 tests
│   ├── test_recommender_v11_training.py  # 10 tests
│   ├── test_bha_compress.py         # 8 tests (auto-skip without BHA runtime)
│   └── test_bha_parallel.py         # 16 tests (4 auto-skip)
├── core_check.py                # Single-source-of-truth verification (8/8 PASS)
├── pyproject.toml               # PEP 517/518 build config
├── INSTALL.md                   # 4 install scenarios + troubleshooting
├── L1-L12-layers.md             # Architecture decomposition
├── benchmark/                    # Telemetry JSON, comparison results
└── tests/README.md               # How to run tests

See `bha_core/README.md` for package-level docs.
```

---

## Running tests

```bash
# All tests (90 pass + 12 skip without BHA runtime)
python -m pytest tests/

# Verbose with coverage
python -m pytest tests/ -v --cov=bha_core --cov-report=term-missing

# Only fast pure-stdlib tests
python -m pytest tests/ -m "not requires_bha"
```

Current coverage (102 tests, 90 pass without BHA runtime):

| Module | Coverage |
|--------|----------|
| `__init__.py` | 100% |
| `recommender_v11.py` | 96% |
| `bha_recommender_v11.py` | 78% |
| `bha_v10_pp_safe.py` | 69% |
| `bha_delta.py` | 66% |
| `bha.py` (needs BHA runtime) | 16% |
| `bha_parallel.py` (needs BHA runtime) | 15% |
| `bha_persistent_pool.py` (needs BHA runtime) | 0% |

---

## Environment variables

| Variable | Default | Purpose |
|----------|---------|---------|
| `PYTHONPATH` | unset | Must include parent of `bha_core/` AND `BHA_RUNTIME_DIR` |
| `BHA_RUNTIME_DIR` | unset | Path to BHA `runtime/` dir with DLL + models |
| `BHA_USE_V11` | `1` | `0` = disable v11, `1` = enable (default) |
| `BHA_V11_ONLY` | `0` | `1` = filter gates to v11 priority only |
| `SSP5_ROOT` | unset | BHA runtime reads this for model files |

---

## License

Project-internal. Source BHA runtime: `D:\PROJECT UNIVERSE\01Compression\BHA\`
(5646 lines, 216KB). bha_core is the production wrapper around it.