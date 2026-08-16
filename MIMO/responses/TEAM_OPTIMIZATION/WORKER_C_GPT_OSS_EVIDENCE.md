# WORKER_C_GPT_OSS_EVIDENCE.md

P0 BENCH-C — raw calibration evidence for **WORKER_C** (OpenRouter gpt-oss-20b).

## Attestation
- worker_id: `MIMO_OPENROUTER_C` (TEST/NON-CANON)
- backend: `openai/gpt-oss-20b` @ openrouter.ai — **PAID variant**
- free `:free` variant rate-limits (HTTP 429) under burst load → paid route used for calibration
- harness: `bench_c_openrouter.py` (9 dims, mirrors BENCH-A/B)

## Results (rounds=3, raw, no self-scoring)

| Dimension | Result | Evidence |
|---|---|---|
| latency | mean 2624.3 ms | values [5517, 1103, 1253] (cold-start spike) |
| failure_rate | 0.0 | 0 failures / 3 |
| code_generation | 3/3 | `compile()` passed |
| code_repair | 2/3 (→ 6/6 re-test) | flaky, see note |
| quality_reasoning | 3/3 | avg-speed → 45 (correct) |
| long_context | 3/3 | "Paris" retrieved 3/3 |
| tool_use | 3/3 full loop | selection→args(7,8)→execution→readback(15) |
| recovery_checkpoint | 3/3 | "RECOVERED" |
| review_catch_rate | 3/3 | caught division-by-zero |
| instruction_adherence | 3/3 | exact "42" |

## Notes (honest)
- **code_repair**: 2/3 in the 3-round bench, but **6/6 in a 6-round re-test**
  (all returned `n * (n + 1) // 2`). Same noise pattern seen with DeepSeek v4-pro —
  a single 3-round miss is not a reliable weakness.
- **429 fix**: free `:free` variant 429s under load; switched to the paid
  `openai/gpt-oss-20b` (same model, no free-tier rate limit). Key is not
  free-tier (`is_free_tier: false`, usage 0.38).

## Files
- `TEAM_OPTIMIZATION/WORKER_C_GPT_OSS_RAW_CALIBRATION.json` (machine-readable)
- `bench_c_openrouter.py` (probe harness, stdlib-only)
