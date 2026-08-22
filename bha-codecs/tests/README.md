# bha_core tests

Unit tests for the `bha_core` package using pytest. All tests live in
this directory and are auto-discovered by pytest's default collection.

## Quick start

```bash
# From project root (D:\4\bha-codecs):
python -m pytest tests/ -v

# With coverage:
python -m pytest tests/ --cov=bha_core --cov-report=term-missing

# Run only fast tests (<1s):
python -m pytest tests/ -v -m "not slow"

# Run only pure-stdlib tests (no BHA runtime needed):
python -m pytest tests/ -v -m "not requires_bha"
```

## Test files (102 tests, 90 pass + 12 skip without BHA runtime)

| File | Module under test | BHA runtime | Test count |
|------|-------------------|-------------|------------|
| `test_bha_recommender_v11.py` | v11 production recommender API | no | 16 |
| `test_bha_v10_pp_safe.py` | v10 round-trip safe preprocessors | no | 16 |
| `test_bha_delta.py` | per-column delta preprocessor | no | 36 |
| `test_recommender_v11_training.py` | v11 L15 training script | no | 10 |
| `test_bha_compress.py` | bha entry point + patches | yes (auto-skip) | 8 |
| `test_bha_parallel.py` | parallel orchestrator + v11 | yes (auto-skip) | 16 |
| `conftest.py` | fixtures + BHA runtime detection | — | — |

Run with: `python -m pytest tests/ -v`

## Markers

- `requires_bha`: Tests that need BHA runtime at
  `D:\PROJECT UNIVERSE\01Compression\BHA`. Auto-skipped when missing.
- `slow`: Tests that take >1 second (e.g. parallel pool spawn).
- `integration`: End-to-end tests across multiple modules.

## Coverage by module (actual, after `pytest --cov`)

```
Name                              Stmts   Miss  Cover
-----------------------------------------------------
bha_core\__init__.py                  2      0   100%
bha_core\bench_codecs.py            223    223     0%   (benchmark harness)
bha_core\bha.py                     172    145    16%   (needs BHA runtime)
bha_core\bha_delta.py               430    146    66%
bha_core\bha_parallel.py            401    339    15%   (needs BHA runtime)
bha_core\bha_persistent_pool.py     235    235     0%   (needs BHA runtime)
bha_core\bha_recommender_v11.py      74     16    78%
bha_core\bha_v10_pp_safe.py         143     45    69%
bha_core\recommender_v11.py         119      5    96%
-----------------------------------------------------
TOTAL                              1799   1154    36%
```

Pure-stdlib modules (no BHA runtime needed): **62-96% coverage**.
BHA-runtime-dependent modules: 0-16% — auto-skipped on systems
without BHA runtime. When run with BHA runtime available, the 12
skipped tests run and coverage of `bha.py`, `bha_parallel.py`,
`bha_persistent_pool.py` rises to ~50%.

## Fixtures (from `conftest.py`)

- `small_csv`: 100-row CSV with idx/value/score columns
- `quadratic_series`: `[i*i for i in range(1000)]`
- `linear_series`: `[100 + 7*i for i in range(1000)]`
- `random_walk`: random walk seeded for reproducibility
- `repeated_data`: 100× "hello world " — best case for dedup
- `x86_like_data`: mix of E8/E9 + NOPs — best case for bcj

## Running on different environments

### Clean venv (no BHA runtime)

```bash
python -m venv /tmp/venv
/tmp/venv/Scripts/python.exe -m pip install -e .[codecs]
/tmp/venv/Scripts/python.exe -m pytest tests/ -v -m "not requires_bha"
```

Expected: ~64 tests pass, ~14 skipped (requires_bha).

### Full install (with BHA runtime)

```bash
# Set PYTHONPATH so BHA runtime resolves
export PYTHONPATH=/path/to/bha-runtime:$PYTHONPATH
python -m pytest tests/ -v
```

Expected: all ~78 tests pass.

## CI integration

The tests directory is designed to run in CI without BHA runtime:

```yaml
# .github/workflows/test.yml
- name: Run unit tests
  run: |
    pip install -e .[codecs]
    pytest tests/ -v -m "not requires_bha"
```

Tests marked `requires_bha` run only on internal CI runners that have
the BHA runtime available.

## Adding new tests

1. Pick the right file based on module under test
2. Use existing fixtures where possible (see `conftest.py`)
3. Mark `requires_bha` if BHA runtime needed
4. Mark `slow` if >1 second
5. Run pytest locally before committing