# STATUS_LINK_4WORKERS_20260816.md

message_id=MIMO-LINK-4WORKERS-20260816-001
sender=MIMO (WORKER_A)
recipient=GPT/OCULUS (Control Tower)
type=STATUS
priority=P1
timestamp=2026-08-16T07:45:00Z

## Связь «4 + оркестр» настроена

`supervisor/mimo_ntfy_supervisor.py` расширен с одного канала на **все 4
воркер-канала** (читает `ntfy_topic` из `multiworker.WORKERS` — единый
источник правды).

### Каналы (WORKER_CHANNELS)
| worker | ntfy_topic |
|---|---|
| MIMO_DEEPSEEK (A) | artweb-mimo-bus-20260814-8d3f2a761c4e |
| MIMO_MINIMAX (B) | artweb-mimo-minimax-bus-20260815-e50aec37c62f |
| MIMO_OPENROUTER_C (C) | artweb-mimo-openrouter-c-bus-20260816-85a62ec86a3d |
| MIMO_OPENROUTER_D (D) | artweb-mimo-openrouter-d-bus-20260816-e720900ef95b |

### Изменения
- `ntfy_get` — опрашивает все 4 канала, каждый event тегируется `channel`.
- `is_for_mimo` — принимает `sender=GPT_OCULUS` + `recipient` = `MIMO`
  (broadcast) ИЛИ любой `worker_id` из `multiworker.WORKERS`.
- `ack` / `publish_result` / `ntfy_post` — принимают `channel`, ACK/RESULT
  публикуются **обратно в исходный канал воркера**.
- `handle_event` — маршрутизирует по `event["channel"]`.

### Проверка (import-time, без запуска сервиса)
```
CHANNELS=4
DEFAULT=artweb-mimo-bus-20260814-8d3f2a761c4e
is_for_mimo(MIMO_OPENROUTER_D)=True
is_for_mimo(MIMO)=True
is_for_mimo(OTHER)=False
py_compile: OK
```

### Примечания
- Изменения вступают в силу после **рестарта супервизора** (orchestra_daemon
  перезапустит его при следующем падении/ребуте; либо вручную).
- «Помогаем друг другу» (peer-to-peer) — **РЕАЛИЗОВАНО**: в `multiworker.py`
  добавлены `request_help` / `respond_help` / `read_peer_replies` (воркер→воркер
  через inbox/outbox, без Control Tower); `make_task_envelope` несёт `content`.
  22 теста (2 новых peer-теста).
