# WORKER_D_GPT4O_MINI_EVIDENCE.md

P0 BENCH-D — raw calibration evidence for **WORKER_D** (OpenRouter gpt-4o-mini).

## Attestation
- worker_id: `MIMO_OPENROUTER_D` (WORKER_D)
- backend: `openai/gpt-4o-mini` @ openrouter.ai (paid)
- harness: `bench_d_openrouter.py` (9 dims, mirrors BENCH-A/B/C)

## Results (rounds=3, raw, no self-scoring)

| Dimension | Result | Evidence |
|---|---|---|
| latency | mean 1285.0 ms | values [1297, 1397, 1161] |
| failure_rate | 0.0 | 0 failures / 3 |
| code_generation | 3/3 | `compile()` passed |
| code_repair | 3/3 | off-by-one fixed |
| quality_reasoning | **0/3** | answers 40/40/48 (correct 45) |
| long_context | 3/3 | "Paris" retrieved |
| tool_use | 3/3 full loop | selection→args→execution→readback |
| recovery_checkpoint | 3/3 | "RECOVERED" |
| review_catch_rate | 3/3 | caught division-by-zero |
| instruction_adherence | 3/3 | exact "42" |

## Highlight (honest)
`quality_reasoning 0/3` is a **REAL weakness** (verified raw answers 40/40/48
vs correct 45), not a heuristic artifact — gpt-4o-mini (small model) fails the
multi-step weighted-average problem. Route math-heavy tasks to A/B/C, not D.

## Files
- `TEAM_OPTIMIZATION/WORKER_D_GPT4O_MINI_RAW_CALIBRATION.json`
- `bench_d_openrouter.py`
