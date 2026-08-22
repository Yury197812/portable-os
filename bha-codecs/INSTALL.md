# Installing and Using bha_core

This document covers four scenarios:

1. **Project-internal use** (the original research project — `D:\4\bha-codecs`)
2. **External project integration** (install bha_core into a different codebase)
3. **Standalone install via pip** (after bha_core is published)
4. **Troubleshooting**

## Prerequisites

- **Python 3.10+** (tested on 3.11.9)
- **Windows** (BHA runtime is Win-only due to `ssp4_fast.dll`; other
  platforms will work but `bench_codecs.py` and `bha_parallel.py` will
  fail to load the BHA runtime — see [Troubleshooting](#troubleshooting))
- **BHA runtime** at `D:\PROJECT UNIVERSE\01Compression\BHA\`:
  - `black_hole_archiver.py` (the runtime entry point)
  - `runtime/` directory with model files and `ssp4_fast.dll`

The BHA runtime is **not** installable from PyPI — it's a
project-internal artifact. Either symlink it, set `PYTHONPATH`, or
copy it next to bha_core.

## Scenario 1 — Project-internal use

You already have the layout:
```
D:\4\bha-codecs\
├── bha_core\         ← production package
├── benchmark\         ← artifacts (telemetry JSON, etc.)
├── core_check.py      ← single-source-of-truth verification
├── pyproject.toml     ← PEP 517/518 build config
├── L1-L12-layers.md   ← architecture docs
└── ...                ← research scripts, tests, corpus
```

### Quick check (already done in this project)

```bash
cd D:\4\bha-codecs
python core_check.py
```

Expected output (8/8 PASS, ~6 minutes):
```
PASS  adaptive int (bha_delta)                            OK (15.9s)
PASS  v10 pp round-trip (bha_v10_pp_safe)                 OK (0.1s)
PASS  persistent pool (bha_persistent_pool)               OK (0.2s)
PASS  parallel orchestrator (bha_parallel)                OK (4.4s)
PASS  v11 recommender API (bha_recommender_v11)           OK (0.1s)
PASS  L15 training (recommender_v11)                      OK (0.5s)
PASS  multi-codec bench (bench_codecs)                    OK (13.0s)
PASS  v10 gates (test_v10_pp_gates)                       OK (326.0s)

8/8 passed
```

### Use from your own scripts in this project

The recommended pattern is `bha_core` package import:

```python
from pathlib import Path
from bha_core import bha, bha_parallel, bha_recommender_v11

# Sequential compression with wall-clock guard
data = Path("foo.csv").read_bytes()
arc, stats, meta = bha.bha_compress(data, src_path=Path("foo.csv"),
                                   total_timeout_s=20)

# Parallel compression (uses v11 recommender by default)
arc, meta = bha_parallel.bha_parallel_compress(
    data, src_path=Path("foo.csv"))

# Get gate recommendations
gates = bha_recommender_v11.recommend("foo.csv", 500_000, k=5)
preset = bha_recommender_v11.lzma_preset_for("foo.csv", 500_000)
```

If you want to run top-level bench scripts that already exist
(`bench_*.py`, `test_v10_pp_gates.py`), they import via `bha_core.*` and
work directly.

## Scenario 2 — External project integration

To use bha_core from a different project (e.g. `D:\my_app\`):

### Step 1 — Install dependencies

```bash
# Required: none (stdlib only)
# Optional: codec packages for full bench_codecs.py support
pip install brotli lz4 zstandard python-snappy zopfli
```

### Step 2 — Make bha_core and BHA runtime importable

Choose **one** of these options:

#### Option A — Symlink into your project's venv site-packages

```bash
# Activate your project's venv
cd D:\my_app
python -m venv .venv
.venv\Scripts\activate

# Symlink bha_core and BHA runtime into site-packages
mklink /J .venv\Lib\site-packages\bha_core D:\4\bha-codecs\bha_core
mklink /J .venv\Lib\site-packages\black_hole_archiver \
       D:\PROJECT UNIVERSE\01Compression\BHA\black_hole_archiver.py
```

But `black_hole_archiver.py` is a single file, not a package, so a
symlink for it alone won't work — you need to set up the runtime
sys.path so the file can be `import`ed. See Option B.

#### Option B — Set `PYTHONPATH` and `BHA_RUNTIME_DIR` env vars

This is the **cleanest portable approach** for a project that doesn't want
to touch site-packages:

```bash
# Windows cmd
set PYTHONPATH=D:\4\bha-codecs;D:\PROJECT UNIVERSE\01Compression\BHA;%PYTHONPATH%
set BHA_RUNTIME_DIR=D:\PROJECT UNIVERSE\01Compression\BHA\runtime

# PowerShell
$env:PYTHONPATH = "D:\4\bha-codecs;D:\PROJECT UNIVERSE\01Compression\BHA;$env:PYTHONPATH"
$env:BHA_RUNTIME_DIR = "D:\PROJECT UNIVERSE\01Compression\BHA\runtime"

# Linux / macOS (BHA runtime won't actually load — see Troubleshooting)
export PYTHONPATH=/path/to/bha-codecs:/path/to/bha-runtime:$PYTHONPATH
export BHA_RUNTIME_DIR=/path/to/bha-runtime/runtime
```

Then in your `setup.cfg`, `pyproject.toml`, or shell, ensure the env
vars are set whenever you import bha_core.

#### Option C — Vendor bha_core into your project

```bash
cp -r D:\4\bha-codecs\bha_core  D:\my_app\third_party\
# Then in D:\my_app\third_party\bha_core\__init__.py you may need to
# adjust the BHA_DIR / RUNTIME_DIR paths.
```

### Step 3 — Verify the install

```python
import sys
import os
from pathlib import Path

# Confirm paths
assert "bha_core" in sys.modules.get("bha_core", type(sys))().__name__, \
    "PYTHONPATH not set correctly"

# Smoke test
from bha_core import bha, bha_parallel, bha_recommender_v11
print(f"bha_core: {bha.__version__ if hasattr(bha, '__version__') else 'OK'}")
print(f"recommender: {bha_recommender_v11.stats()}")
```

## Scenario 3 — Standalone install via pip

After bha_core is published to a private index (or PyPI):

```bash
# From a project that needs bha_core:
pip install bha-core

# With optional codec packages:
pip install "bha-core[codecs]"

# With everything:
pip install "bha-core[all]"
```

Then in your code:
```python
from bha_core import bha, bha_parallel, bha_recommender_v11
# ... as in Scenario 1
```

The installed package brings:
- All 8 modules of `bha_core/` (bha, bha_delta, bha_v10_pp_safe,
  bha_parallel, bha_persistent_pool, bha_recommender_v11,
  recommender_v11, bench_codecs)
- `catalog.ini` (codec catalog)
- `rules.json` (v11 trained rules — see note below)
- `__init__.py` with `__version__ = '1.0'`
- `README.md` (this is the long-form docs)

### Publishing bha_core to a private index

```bash
cd D:\4\bha-codecs
python -m build
twine upload --repository-url https://your-private-pypi dist/*
```

The `pyproject.toml` in this project is already configured for `setuptools>=61.0` build backend.

### What `rules.json` is and when to retrain

`rules.json` is the output of `recommender_v11.py` L15 training. It
contains per-extension codec distribution learned from the 50-file BHA
corpus. It's used by `bha_recommender_v11.recommend()` to prioritize
gates.

`rules.json` and `catalog.ini` are **bundled with the wheel** via
`[tool.setuptools.package-data]` in `pyproject.toml`. After
`pip install bha-core`, they sit next to the .py files in
`site-packages/bha_core/`. The package loads them at runtime via
`Path(__file__).parent / NAME`, so the install is self-contained.

If your project uses a different corpus or you want to retrain on more
data:

```bash
# 1. Collect telemetry from your corpus:
python -m bha_core.bench_codecs \
       --iter 3 --max-file-size 1000000 \
       --out /path/to/your/telemetry.json

# 2. Patch the training script's TELEMETRY path:
#    Edit bha_core/recommender_v11.py line ~32:
#    TELEMETRY = Path('/path/to/your/telemetry.json')

# 3. Retrain v11:
python -m bha_core.recommender_v11
# This overwrites bha_core/rules.json with new rules.
```

## Scenario 4 — As a CLI tool

After installing with pip, you get two console scripts:

```bash
# Pack a single file with wall-clock guard:
bha-pack foo.csv
# Output: foo.csv.bha + JSON stats

# Run parallel orchestrator on one or more files:
bha-orchestrate foo.csv bar.json baz.html
# Per-file: best gate, size, timing
```

Both are entry points declared in `pyproject.toml`:
```toml
[project.scripts]
bha-pack = "bha_core.bha:_cli"
bha-orchestrate = "bha_core.bha_parallel:_cli"
```

## Environment variables

| Variable | Default | Purpose |
|----------|---------|---------|
| `PYTHONPATH` | unset | Must include parent of `bha_core/` AND `BHA_RUNTIME_DIR` |
| `BHA_RUNTIME_DIR` | unset | Should point to BHA `runtime/` dir with DLL + models |
| `BHA_USE_V11` | `1` | Set to `0` to disable v11 recommender (run all gates) |
| `BHA_V11_ONLY` | `0` | Set to `1` to filter gates to v11 priority only |
| `SSP5_ROOT` | unset | BHA runtime reads this to locate model files |

## Testing the install in a clean venv (recommended)

To verify the install is fully self-contained:

```bash
# 1. Create a clean venv (no project imports)
python -m venv /tmp/bha_test_venv

# 2. Install the wheel
/tmp/bha_test_venv/Scripts/python.exe -m pip install \
        /path/to/dist/bha_core-1.0.0-py3-none-any.whl

# 3. Verify package + data files
/tmp/bha_test_venv/Scripts/python.exe -c "
import bha_core
import zipfile, sys
# Check that data files ship with the wheel
whl = '/path/to/dist/bha_core-1.0.0-py3-none-any.whl'
with zipfile.ZipFile(whl) as z:
    names = z.namelist()
    assert any('catalog.ini' in n for n in names), 'catalog.ini missing!'
    assert any('rules.json' in n for n in names), 'rules.json missing!'
print('wheel contents OK')
"

# 4. Run the CLI scripts
/tmp/bha_test_venv/Scripts/bha-pack.exe --help
/tmp/bha_test_venv/Scripts/bha-orchestrate.exe --help
```

Expected output for the CLI checks:

```
usage: bha [-h] [--bench] [--iter ITER] [--budget BUDGET] [--json] [files ...]
...
usage: bha-orchestrate [-h] [--max-workers MAX_WORKERS] files [files ...]
```

## Testing the install

A one-liner to verify the package works end-to-end:

```python
from pathlib import Path
from bha_core import bha, bha_parallel, bha_recommender_v11

# Recommender API (no BHA runtime needed)
gates = bha_recommender_v11.recommend("test.csv", 500_000)
print(f"v11 gates: {gates}")
preset = bha_recommender_v11.lzma_preset_for("test.csv", 500_000)
print(f"v11 LZMA preset: {preset}")
assert gates == ['delta_pp', 'lzma_fallback', 'telemetry_csv', 'quoted_csv', 'tabular_col']

# Round-trip via bha_v10_pp_safe (no BHA runtime needed)
from bha_core import bha_v10_pp_safe
data = b"hello world " * 100
pre, side = bha_v10_pp_safe.pp_dedup_substring_safe(data)
decoded = bha_v10_pp_safe.decode_dedup_substring(pre, side)
assert decoded == data

# Full pipeline (BHA runtime needed)
from bha_core import bha_parallel
data = Path("test.csv").read_bytes()
arc, meta = bha_parallel.bha_parallel_compress(data)
print(f"compressed: {len(arc)} bytes via {meta['best_gate']}")
```

If this prints and exits cleanly, your install is correct.

## Troubleshooting

### "ModuleNotFoundError: No module named 'black_hole_archiver'"

The BHA runtime file `black_hole_archiver.py` is not on `PYTHONPATH`.

**Fix**:
```bash
# Add the BHA directory to PYTHONPATH (one-time):
set PYTHONPATH=D:\PROJECT UNIVERSE\01Compression\BHA;%PYTHONPATH%

# Or in your Python script:
import sys
sys.path.insert(0, r"D:\PROJECT UNIVERSE\01Compression\BHA")
import black_hole_archiver  # now works
```

### "FileNotFoundError: ssp4_fast.dll" or model files missing

The BHA runtime needs its `runtime/` subdirectory on the env var
`SSP5_ROOT`.

**Fix**:
```bash
set SSP5_ROOT=D:\PROJECT UNIVERSE\01Compression\BHA\runtime
```

The BHA runtime contains these critical files (all in `runtime/`):
- `ssp4_fast.dll` — native compression library
- `ssp4_local_v44.py` — Python wrapper
- `kn_english_4gram.bin` (4MB) — language model
- `lstm_gutenberg.bin` (8MB) — language model
- Plus several other model files

If any are missing, BHA falls back to LZMA-only mode and most
preprocessor gates are disabled.

### "ModuleNotFoundError: No module named 'brotli'" / 'zstandard' / etc.

Optional codec packages are missing. Install them:

```bash
pip install brotli lz4 zstandard python-snappy zopfli
```

These are listed as `extras_require` in `pyproject.toml` — install
`bha-core[codecs]` for everything.

### "ImportError: attempted relative import with no known parent package"

You're trying to import a bha_core module directly (not as a package):

```python
# BAD:
import bha_delta  # ModuleNotFoundError because bha_delta is a submodule

# GOOD:
from bha_core import bha_delta
# or
import bha_core.bha_delta
```

### Linux / macOS

BHA runtime is **Windows-only** because of `ssp4_fast.dll`. On
Linux/macOS:

- `bha_core.bha_recommender_v11` works — pure stdlib + JSON
- `bha_core.recommender_v11` works — pure stdlib + JSON
- `bha_core.bha_v10_pp_safe` works — pure stdlib
- `bha_core.bha_delta` works — pure stdlib
- `bha_core.bha_parallel`, `bha_core.bha_persistent_pool`,
  `bha_core.bha`, `bha_core.bench_codecs` — **require BHA runtime**,
  will fail at `_load_runtime()` on non-Windows

Use `bha_recommender_v11`,` `recommender_v11`,` `bha_v10_pp_safe`,` `bha_delta`
cross-platform. Avoid the others.

### Performance is slower than expected

- For the **parallel orchestrator**, ensure `ProcessPoolExecutor`
  workers can spawn. On Windows, use Python 3.11+ (3.10 has spawn issues).
- The `bha_persistent_pool` module gives 2.14× speedup over per-call
  pools because it avoids the 200ms × N spawn cost. Use it instead of
  `bha_parallel` for repeated calls on the same process.

### Encoder/decoder size mismatch

You're using a preprocessor (`decoder_x`) that doesn't match its
encoder (`encoder_x`). For each `pp_*_safe` encoder there is a
matching `decode_*` function — use them as a pair.

## What bha_core does NOT include

- The BHA runtime itself (`D:\PROJECT UNIVERSE\01Compression\BHA\`)
- `L1-L12-layers.md` (architecture doc — in parent project)
- `core_check.py` (verification script — in parent project)
- `benchmark/` (artifacts and test corpus — in parent project)
- Research scripts (`investigate_ssp5_*.py`, `corpus_*.py`, etc.)

These are part of the larger `D:\4\bha-codecs\` research project, not
the production package. To use bha_core, only the package itself is
required; the rest is for development and benchmarking.