# MINIMAX_M3_EVIDENCE.md

P0 BENCH-B — raw calibration evidence for **MiniMax-M3** (WORKER_B backend).

## Attestation
- worker_id: `MIMO_MINIMAX` (WORKER_B)
- actual backend: `MiniMax-M3` @ `api.minimax.io/v1/chat/completions`
- engine: MIMO (MiMoCode CLI)
- harness: `bench_b_minimax.py` (mirrors BENCH-A's 9 dimensions; `<think>` stripped, `base_resp` error checked)

## Results (rounds=3, raw, no self-scoring)

| Dimension | Result | Evidence |
|---|---|---|
| latency | mean 2071.7 ms | values [2967, 1631, 1617] |
| failure_rate | 0.0 | 0 failures / 3 |
| code_generation | 3/3 | `compile()` passed on emitted function |
| code_repair | 3/3 | off-by-one fixed 3/3 |
| quality_reasoning | 3/3 | avg-speed → 45 (correct) |
| long_context | **2/3** | "Paris" retrieved 2 of 3 rounds |
| tool_use | 3/3 full loop | selection→args(7,8)→execution→readback(15) |
| recovery_checkpoint | 3/3 | emitted "RECOVERED" |
| review_catch_rate | 3/3 | caught seeded division-by-zero |
| instruction_adherence | 3/3 | exact "42" |

## Highlight (honest)
`long_context` is the weakest observed dimension: 2/3 (one miss retrieving "Paris"
from a 5K-token prompt). Minor, but flag for GPT to consider for long-context
retrieval tasks. All other dimensions 3/3 — including `tool_use` (supported,
full loop clean).

## Files
- `TEAM_OPTIMIZATION/MINIMAX_M3_RAW_CALIBRATION.json` (machine-readable)
- `bench_b_minimax.py` (probe harness, stdlib-only)
