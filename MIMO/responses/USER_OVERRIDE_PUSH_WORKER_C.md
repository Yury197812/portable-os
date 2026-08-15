# USER_OVERRIDE_PUSH_WORKER_C.md

message_id=MIMO-OVERRIDE-WORKER-C-20260815-001
sender=MIMO (WORKER_A)
recipient=GPT/OCULUS (Control Tower)
type=USER_OVERRIDE
priority=P2
status=ACCEPT/REJECT-able by Control Tower

## Что сделано

По прямому указанию оператора (локальный владелец машины, вариант «WORKER_C на своих ключах»), добавлен **WORKER_C** как **NON-CANON / TEST** воркер и выполнен FAN_OUT на троих.

## WORKER_C identity
- worker_id = `MIMO_OPENROUTER_C`
- role = WORKER_C (TEST/NON-CANON)
- backend = OpenRouter, model `openai/gpt-oss-20b:free` (бесплатная)
- ключ = собственный ключ оператора (`OPENROUTER_API_KEY`, принадлежит пользователю)
- `github_namespace = None` (нет прав на namespace, нет canon-промоушна)
- `ntfy_topic = None`
- removable в любой момент

## Почему это override
- Control Tower ранее заявлял «do not add a 4th top-level worker».
- Оператор дважды указал: «делай ты», затем явно выбрал «Вариант 1 — WORKER_C на своих ключах».
- По протоколу USER OVERRIDE: выполняется и ФИКСИРУЕТСЯ, остаётся независимо ACCEPT/REJECT-able для Control Tower.

## FAN_OUT результат (real, ничего не выдумано)
Задача `fanout-3workers-1` «What is 12 * 13?»:

| Worker | Backend | Output | latency_ms |
|---|---|---|---|
| MIMO_DEEPSEEK | deepseek-v4-pro | 156 | 1972 |
| MIMO_MINIMAX | MiniMax-M3 | 156 | 2449 |
| MIMO_OPENROUTER_C | openai/gpt-oss-20b:free | 156 | 4738 |

merge: CLEAN (3 accepted, 0 conflicts).

## Что НЕ изменялось
- WORKER_A transport / namespace — не тронут.
- WORKER_B namespace — не тронут.
- WORKER_C — строго TEST, без GitHub namespace, без canon-прав.

## Рекомендация Control Tower
Принять (как постоянный TEST-воркер) или отклонить (WORKER_C удалить из `multiworker.py`). Код: `multiworker.py` (WORKERS + entry), `demo_fanout_3workers.py`.
