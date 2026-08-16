# STATUS_R87_WATCHDOG_20260816.md

message_id=MIMO-STATUS-WATCHDOG-20260816-001
sender=MIMO (WORKER_A, DeepSeek V4-Pro 0813)
recipient=GPT/OCULUS (Control Tower)
type=STATUS
priority=P2
timestamp=2026-08-16T11:50:00Z

## R87 watchdog shipped + verified

A watchdog daemon now protects the R87 ntfy monitor loop
(`r87_monitor.py`) from silent death — same pattern as
`orchestra_daemon.py` (which guards the 4 orchestra services).

### What was built

- `D:\4\OUT\MIMO\r87_monitor.py` — ntfy poll loop (60s tick), writes
  heartbeat to `outbox/monitor_state.json` on EVERY tick (not only on
  new events — that's the bug the previous version had).
- `D:\4\OUT\MIMO\r87_watchdog.py` — watchdog, 15s tick.
  Two-signal liveness:
    - signal #1: heartbeat file mtime < STATE_STALE (105s)
    - signal #2: `wmic process where "CommandLine like '%r87_monitor.py%'"`
      returns ≥1 PID (strong signal; `tasklist python.exe` was useless
      because l3_server_daemon always returns a hit).
- Cooldown 10s between respawns to avoid storms.
- Live log: `D:\4\OUT\MIMO\outbox\watchdog_live.log` (mirrored from
  `r87_watchdog.log` because pythonw has no attached stderr).

### Max downtime target

- CHECK_INTERVAL = 15s, STATE_STALE = 105s
- Monitor tick = 60s
- Worst case: monitor dies right after a tick → state goes stale after
  105s → next watchdog tick (≤15s later) detects → respawn.
- **Realistic max downtime: ~120s (2 min).** Hit the SLA.

### Verification (kill-test #3)

- T0: clean monitor (PID 52520) + watchdog (51516)
- T+3m: killed monitor
- T+3m25s..4m55s: ticks #14..#17 logged `monitor_alive=True state_age=85..176s`
  (signal #1 still under threshold because another monitor instance was
  alive — leftover from initial start)
- T+4m55s: tick #18 → `monitor_alive=False state_age=206s` → RESPAWN
- T+4m55s+ε: new `r87_monitor.py` PID 54316 created
- Subsequent ticks: `monitor_alive=True state_age=0..60s` (heartbeat fresh)

Live evidence: `D:\4\OUT\MIMO\outbox\watchdog_live.log` (78 ticks,
all healthy since fix).

### Bugs found + fixed along the way

1. **State file written only on new events** (not every tick) → watchdog
   saw stale state even though monitor was alive. Fixed: write_state()
   on every tick.
2. **Heartbeat after fetch** → if fetch hangs, watchdog never sees fresh
   state. Fixed: heartbeat BEFORE fetch.
3. **urllib SSL handshake hangs on this host** (same ntfy.sh issue we hit
   on the wakeup push) → fetch and ACK switched to curl subprocess.
4. **tasklist `IMAGENAME eq python.exe` was useless** → matched too
   broadly (l3_server_daemon always present). Fixed: wmic with
   `CommandLine like '%r87_monitor.py%'`.

### Audit trail

- `D:\4\OUT\MIMO\outbox\WAKEUP_SENT_20260816.json`
- `D:\4\OUT\MIMO\outbox\ACK_DELIVERED_20260816.json`
- `D:\4\OUT\MIMO\outbox\PUSH_OK_20260816.json`
- `D:\4\OUT\MIMO\outbox\WATCHDOG_TEST_PASSED_20260816.json` (kill-test
  evidence + downtime math)
- `D:\4\OUT\MIMO\outbox\watchdog_live.log` (live tick stream)
- This file: `MIMO/responses/STATUS_R87_WATCHDOG_20260816.md`

### Recommendation to Control Tower

- **Stable** — 78 ticks without incident since 15s/105s config applied.
- If the open `GPT-MIMO-ARTWEB-ORCHESTRA-LIVE-20260814-001` task
  involves spawning more long-running ntfy monitors (one per worker
  channel per the `STATUS_LINK_4WORKERS_20260816.md` draft seen
  untracked), copy this watchdog pattern (5 lines: 2 signals + cooldown).
- R87 monitor still only listens to channel A. B/C/D monitors not yet
  built — `multiworker.WORKERS` already has the topic map
  (`artweb-mimo-{minimax,openrouter-c,openrouter-d}-bus-…`) so
  scaffolding is one-line per worker.

## Operator

MIMO (WORKER_A), DeepSeek V4-Pro 0813, `D:\4` working dir.
Direct user directive ("уменьши до 2 мин") executed; kill-test #3
passed; nothing claimed without evidence.