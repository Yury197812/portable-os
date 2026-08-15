# DEEPSEEK_V4_PRO_EVIDENCE.md

P0 BENCH-A — raw calibration evidence for `deepseek-v4-pro` (exact backend).

## Attestation
- worker_shell: MIMO (MiMoCode CLI)
- actual backend: `deepseek-v4-pro` @ `api.deepseek.com/v1/chat/completions`
- NOT proxied through qwen/Ollama (identity corrected from earlier session)

## Results (rounds=3, raw, no self-scoring)

| Dimension | Result | Evidence |
|---|---|---|
| latency | mean 2014.3 ms | values [2271, 1871, 1901] |
| failure_rate | 0.0 | 0 failures / 3 |
| code_generation | 3/3 | `compile()` passed on emitted `fibonacci` |
| code_repair | **1/3** | off-by-one fix only correct 1 of 3 rounds |
| quality_reasoning | 3/3 | avg-speed word problem → 45 (correct) |
| long_context | 3/3 | retrieved "Paris" from tail of 5K-token prompt |
| tool_use | 3/3 full loop | selection→args(7,8)→execution→readback(15) all 3/3 |
| recovery_checkpoint | 3/3 | resumed and emitted "RECOVERED" |
| review_catch_rate | 3/3 | caught seeded division-by-zero bug |
| instruction_adherence | 3/3 | exact "42" output |

## Highlight (honest)
`code_repair` is the weakest observed dimension: on a seeded off-by-one
defect, the model fully corrected it only 1/3 times. This is raw evidence,
not a score — flag for GPT to consider in task routing (avoid assigning
DeepSeek v4-pro to heavy code-repair tasks without review).

## Files
- `TEAM_OPTIMIZATION/DEEPSEEK_V4_PRO_RAW_CALIBRATION.json` (machine-readable)
- `bench_a_deepseek.py` (probe harness, stdlib-only)
