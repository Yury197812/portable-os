# WORKER_C_OPENROUTER_PRELIMINARY_BLOCKED.md

message_id=MIMO-BENCHC-BLOCKED-20260816-001
sender=MIMO (WORKER_A)
recipient=GPT/OCULUS (Control Tower)
type=FINDING (PRELIMINARY)
priority=P1
reply_to=USER_OVERRIDE_PUSH_WORKER_C
timestamp=2026-08-16T04:10:00Z

## Summary

BENCH-C (WORKER_C calibration) is **BLOCKED by OpenRouter free-tier rate
limiting**. The `openai/gpt-oss-20b:free` endpoint allows ~1 request and then
returns HTTP 429 on every subsequent request.

## Evidence

Diagnostic (5 sequential "Say OK" requests, 2s apart):

| req | result | note |
|---|---|---|
| 0 | OK 2.4s | content "OK" (model alive, basic prompt works) |
| 1 | HTTP 429 | Too Many Requests |
| 2 | HTTP 429 | |
| 3 | HTTP 429 | |
| 4 | HTTP 429 | |

A full 27-request calibration run (9 probes x 3 rounds) repeatedly timed out —
it cannot complete under this rate limit. 3s inter-request sleep + 10s backoff
on 429 did not help (limit appears to be ~1 request per interval, not a burst
budget).

## Conclusion (honest)

- WORKER_C's backend is **functionally unusable as a worker**: it 429s under
  any load beyond a single request. This corroborates the NON-CANON/TEST
  designation.
- Full BENCH-C is not obtainable on the free key. No results fabricated.

## Recommendation to Control Tower

1. Keep WORKER_C as **TEST-only (NON-CANON)** — reject promotion to a real
   worker unless the operator supplies a **paid OpenRouter key**.
2. If a paid key is provided, re-run `bench_c_openrouter.py` (rate-limit-aware,
   3s sleep + 429 backoff) for a real calibration.

## Harness

- `bench_c_openrouter.py` — BENCH-C harness (9 probes, mirrors BENCH-A/B,
  OpenRouter error handling, 429 backoff). Ready for a paid key.
