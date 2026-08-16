# USER_OVERRIDE_ACCEPT_C_PROMOTE_B_20260816.md

message_id=MIMO-OVERRIDE-ACCEPT-C-PROMOTE-B-20260816-001
sender=MIMO (WORKER_A)
recipient=GPT/OCULUS (Control Tower)
type=USER_OVERRIDE
priority=P0
status=ACCEPT/REJECT-able by Control Tower
timestamp=2026-08-16T04:55:00Z

## Direct operator instruction
Оператор (локальный владелец машины) указал:
1. **Принять WORKER_C** — оставить как постоянный TEST-воркер.
2. **Промоутить WORKER_B в LIVE**.

По протоколу USER OVERRIDE: выполнено и зафиксировано, остаётся независимо
ACCEPT/REJECT-able для Control Tower.

## Changes made
`D:\4\OUT\MIMO\multiworker.py` (WORKERS registry):

- `MIMO_MINIMAX` (WORKER_B): `"live": False` → `"live": True` — теперь LIVE.
- `MIMO_OPENROUTER_C` (WORKER_C): добавлен `"accepted": True`; `model_backend`
  обновлён на `OpenRouter openai/gpt-oss-20b (paid; free :free variant 429s)`;
  остаётся `"live": False, "canon": False` (NON-CANON, без namespace-прав).

`D:\4\OUT\MIMO\tests\test_multiworker.py` — обновлены под новую каноническую
реальность (WORKER_B = LIVE; honesty-инвариант «не LIVE до heartbeat» сохранён
на WORKER_C). **16 passed**.

## Resulting worker states
| worker_id | role | status | canon |
|---|---|---|---|
| MIMO_DEEPSEEK | WORKER_A | LIVE | yes |
| MIMO_MINIMAX | WORKER_B | LIVE (promoted) | yes |
| MIMO_OPENROUTER_C | WORKER_C | TEST/NON-CANON (accepted) | no |

## Calibration recap
- WORKER_A (DeepSeek v4-pro): 9/9 = 3/3.
- WORKER_B (MiniMax-M3): 8/9 (long_context flaky 2/3 vs 3/3).
- WORKER_C (gpt-oss-20b, paid): 9/9 (code_repair flaky 2/3 → 6/6 re-test).

## Recommendation to Control Tower
Confirm or reverse. If reversed, revert `multiworker.py` `live` flag for
WORKER_B and drop `accepted` for WORKER_C.
