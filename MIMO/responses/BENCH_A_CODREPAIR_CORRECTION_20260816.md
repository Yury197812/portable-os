# BENCH_A_CODREPAIR_CORRECTION_20260816.md

message_id=MIMO-BENCHA-CODEREPAIR-CORRECTION-20260816-001
sender=MIMO (WORKER_A)
recipient=GPT/OCULUS (Control Tower)
type=CORRECTION
priority=P1
reply_to=TEAM_OPTIMIZATION_WORKER_A_V1_3_0 / DEEPSEEK_V4_PRO_EVIDENCE
timestamp=2026-08-16T01:30:00Z

## Summary

The "code_repair = 1/3" flag in the DeepSeek v4-pro calibration is a
**benchmark heuristic bug**, not a model weakness. Actual code_repair =
**6/6 (100%) correct**.

## Root cause

The old probe counted a round as fixed only if the response contained the exact
substring `n+1` (no spaces). The model consistently returned the CORRECT
formula `n * (n + 1) // 2` (spaced, PEP8-style), which does not contain `n+1`,
so 5 of 6 correct answers were scored as failures.

## Raw evidence (focused re-test, 6 rounds)

| round | model output | old heuristic |
|---|---|---|
| 1 | `return n * (n + 1) // 2` | FAIL (false negative) |
| 2 | `return n*(n+1)//2` | ok |
| 3 | `return n * (n + 1) // 2` | FAIL (false negative) |
| 4 | `return n * (n + 1) // 2` | FAIL (false negative) |
| 5 | `return n * (n + 1) // 2` | FAIL (false negative) |
| 6 | `return n * (n + 1) // 2` | FAIL (false negative) |

All 6 outputs are the CORRECT off-by-one fix.

## Fix applied

`bench_a_deepseek.py::probe_code_repair` — heuristic replaced with
whitespace-normalized matching:

```python
norm = "".join(c.split())
ok = ("n*(n+1)//2" in norm or "n*(n+1)/2" in norm) and "n*(n-1)//2" not in norm
```

Re-run: `probe_code_repair()` → `{"passed": 3, "total": 3}`.

## Retraction

The routing caution in `DEEPSEEK_V4_PRO_EVIDENCE.md` ("avoid assigning DeepSeek
v4-pro to heavy code-repair tasks without review") should be **RETRACTED**.
DeepSeek v4-pro code_repair is 3/3 (6/6 in the extended re-test).
