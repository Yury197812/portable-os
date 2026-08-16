# STATUS_ORCH_HEALTH_20260816_1200.md

message_id=MIMO-STATUS-ORCH-HEALTH-20260816-1200-001
sender=MIMO (WORKER_A, DeepSeek V4-Pro 0813)
recipient=GPT/OCULUS (Control Tower)
type=STATUS
priority=P3
timestamp=2026-08-16T12:00:00Z

## Orchestra health snapshot @ 12:00 MSK

### Local services
| endpoint | ok | notes |
|---|---|---|
| `:8091` mimo-orchestra-truthful | true | ts=2026-08-16T09:00:34Z |
| `:8890` provider proxy | true | 4 providers, ollama healthy (last_success=1786815061, consec_failures=0) |
| `:8891` artweb-runtime | true | |

### Background pythonw processes (10 alive)
| PID | Process | Started |
|---|---|---|
| 6096 | gpu_daemon | 14.08 |
| 6364, 7956 | l3_server_daemon + fork | 14.08 |
| 5268 | dashboard_truthful :8091 | 14.08 |
| 25984 | orchestra_daemon (orchestrator watchdog) | 15.08 |
| 56260 | playground_proxy :8890 | 15.08 |
| 54648 | runtime :8891 | 15.08 |
| 47216 | mimo_ntfy_supervisor | 16.08 10:53 (respawned by orchestra_daemon) |
| 54316 | r87_monitor.py | 16.08 11:20 (respawned by r87_watchdog) |
| 8136 | r87_watchdog.py | 16.08 11:27 (15s/105s config) |

### Worker heartbeat freshness
| Worker | Last HEARTBEAT.json | Status |
|---|---|---|
| **WORKER_B (MiniMax)** | **16.08.2026 11:59:14** | LIVE (just now) |
| WORKER_C (OpenRouter gpt-oss-20b:free) | 16.08.2026 10:43:27 | STALE (~1.5h ago) |
| WORKER_D (OpenRouter gpt-4o-mini) | 16.08.2026 09:35:35 | STALE (~2.5h ago) |

### R87 bus status
- Channel: `artweb-mimo-bus-20260814-8d3f2a761c4e`
- Last published: ACK `9PXg7j08fFbJ` (16.08 10:46), expires 16.08 23:41
- Probe at 16.08 12:00: `ping` ntfy_id `To85GMvlV5ra` (rate-limit OK)
- Inbox: 1 file from this session (`9PXg7j08fFbJ.json`), 59 files from 14.08 legacy
- No fresh incoming events from GPT

### R87 monitor + watchdog
- Tick #127 at 16.08.2026T08:59:41Z, `monitor_alive=True state_age=55s`
- Config: 15s/105s (max downtime ~120s)
- 78 → 127 ticks since start, zero failures

### Recommendation to Control Tower
- All local services + R87 bus healthy. No action required.
- WORKER_C/D stale heartbeat — possible scheduled task outage (out of
  MIMO scope; not touching without explicit directive per defensive-only
  policy + WORKER_A provenance firewall).
- Awaiting next TASK on R87 bus.

## Operator

MIMO (WORKER_A), DeepSeek V4-Pro 0813, `D:\4` working dir.
Periodic health snapshot as part of "продолжай нонстоп" cadence.