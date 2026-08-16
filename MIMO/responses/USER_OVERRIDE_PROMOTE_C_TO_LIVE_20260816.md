# USER_OVERRIDE_PROMOTE_C_TO_LIVE_20260816.md

message_id=MIMO-OVERRIDE-PROMOTE-C-TO-LIVE-20260816-001
sender=MIMO (WORKER_A)
recipient=GPT/OCULUS (Control Tower)
type=USER_OVERRIDE
priority=P0
status=ACCEPT/REJECT-able by Control Tower
timestamp=2026-08-16T05:05:00Z

## Direct operator instruction
Оператор указал: **промоутить WORKER_C в LIVE**.

По протоколу USER OVERRIDE: выполнено и зафиксировано, остаётся независимо
ACCEPT/REJECT-able для Control Tower.

## Changes made
`D:\4\OUT\MIMO\multiworker.py` (WORKERS registry), WORKER_C:
- `"live": False` → `"live": True` — теперь LIVE.
- `role`: `"WORKER_C (TEST/NON-CANON)"` → `"WORKER_C"`.
- комментарий обновлён.

`D:\4\OUT\MIMO\tests\test_multiworker.py` — тесты C актуализированы
(`test_worker_c_is_live`, `test_register_worker_c_sets_instance`). **16 passed**.

## Resulting worker states
| worker_id | role | status | canon | namespace/ntfy |
|---|---|---|---|---|
| MIMO_DEEPSEEK | WORKER_A | LIVE | yes | MIMO/responses/ + ntfy |
| MIMO_MINIMAX | WORKER_B | LIVE | yes | MIMO/workers/MIMO_MINIMAX/ + ntfy |
| MIMO_OPENROUTER_C | WORKER_C | LIVE | **no** | **None / None** |

## Flag (honest)
WORKER_C is now LIVE at the **coordination layer**, but `github_namespace=None`
and `ntfy_topic=None` — it has **no transport** (can't push results to GitHub,
no ntfy channel). This is a LIVE-but-no-transport state. If WORKER_C should be
a full canon participant, the Control Tower must assign a namespace + ntfy
topic and set `canon: True`.

## Recommendation to Control Tower
Confirm or reverse. To reverse: `live: False` + restore role. To fully
canon-ify WORKER_C: assign `github_namespace`, `ntfy_topic`, and `canon: True`.
