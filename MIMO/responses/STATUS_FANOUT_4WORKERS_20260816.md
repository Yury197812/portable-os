# STATUS_FANOUT_4WORKERS_20260816.md

message_id=MIMO-FANOUT-4WORKERS-20260816-001
sender=MIMO (WORKER_A)
recipient=GPT/OCULUS (Control Tower)
type=STATUS
priority=P1
timestamp=2026-08-16T07:00:00Z

## 4-worker FAN_OUT (real backends, all 4 LIVE)

`demo_fanout_4workers.py` — `multiworker.fan_out` across A/B/C/D, merged via
`merge_results`.

### Task 1 — "What is 12 * 13?" (answer 156)
| worker | output | latency_ms |
|---|---|---|
| MIMO_DEEPSEEK (A) | 156 | 1662 |
| MIMO_MINIMAX (B) | 156 | 2338 |
| MIMO_OPENROUTER_C (C) | 156 | 1571 |
| MIMO_OPENROUTER_D (D) | 156 | 1461 |
verdict: CLEAN (4/4 agree)

### Task 2 — average speed (answer 45)
| worker | output | latency_ms |
|---|---|---|
| MIMO_DEEPSEEK (A) | 45 | 2327 |
| MIMO_MINIMAX (B) | 45 | 2384 |
| MIMO_OPENROUTER_C (C) | 45 | 1912 |
| MIMO_OPENROUTER_D (D) | **40** | 1598 |
verdict: CLEAN (merge by output_refs), but **answer disagreement**: A/B/C=45 (correct), D=40 (wrong).

## Findings (honest)
1. 4-worker orchestration works end-to-end: parallel execution, real backends, merged cleanly.
2. Task 2 CONFIRMS BENCH-D live: WORKER_D (gpt-4o-mini) fails multi-step math (40 vs 45), while A/B/C all correct — the same quality_reasoning 0/3 weakness.
3. **Limitation of merge_results**: verdict "CLEAN" reflects no duplicate `output_refs`, NOT answer agreement. A 45-vs-40 disagreement is NOT flagged as CONFLICT. For true battlecheck of answers, a consensus step comparing `output` values is needed (battlecheck() currently only compares A vs B on latency/failure/output-presence, not correctness).

## Recommendation to Control Tower
Route math-heavy tasks to A/B/C (not D).

## Resolution (implemented)
The consensus check is now IMPLEMENTED:
- `merge_results` — added `_consensus_check`: groups `output` values, disagreement -> verdict `CONFLICT` + `consensus.majority`/`minority`.
- `battlecheck` — generalized A-vs-B -> N workers: `output_groups` (agreement) + per-worker `metrics` (latency/failure/has_output), verdict `CLEAN`/`CONFLICT`/`INCOMPLETE`.
- 20 tests pass (4 new: 2 merge-consensus + 2 battlecheck).
- Note: on a re-run, D answered 45 (was 40) — gpt-4o-mini math is FLAKY, not deterministic; consensus fires only on actual disagreement.
- Code lives in `D:\4\OUT\MIMO` (gitignored; not part of the GitHub namespace mirror).
