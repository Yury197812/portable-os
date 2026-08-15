# OCULUS v1.0.2 proposal — heartbeat-loop GitHub push flakiness fix

proposal_id: PROPOSAL-OCULUS-2026-08-15-V1.0.2-HEARTBEAT-PUSH
proposal_status: **WITHDRAWN** (baseline established, failure NOT REPRODUCED)
proposal_author: mimocode (orchestrator)
proposal_date: 2026-08-15
proposal_decided: 2026-08-15T23:29Z

## 1. Problem statement

The `MIMO_HEARTBEAT_B` Scheduled Task writes `D:\4\OUT\MIMO_MINIMAX\status\HEARTBEAT.json` every 2 minutes (last verified `LAST_RUN=23:15:15`, `LAST_RESULT=0`). When the file is also pushed to GitHub via `gh api PUT`, the push fails ~50% of the time with one of:
- HTTP 400 "Problems parsing JSON" (LF vs CRLF mismatch — see MEMORY.md line 81)
- TLS handshake timeout on `gh auth refresh` device-flow

This is documented in MEMORY.md line 81 ("Heartbeat-loop GitHub push flakiness") and checkpoint.md §8 Errors and fixes.

## 2. Proposed change

Add a `gh auth refresh --user github.com --with-token` retry hook in `D:\4\OUT\MIMO_MINIMAX\status\heartbeat.ps1` that:
- (a) reads existing `gh auth status` exit code on push failure
- (b) if status non-zero, runs `gh auth refresh --user github.com --hostname github.com` (no-op if already valid)
- (c) retries the push once (single retry; not infinite loop)

This avoids the systematic dependency on the user running `gh auth refresh` interactively. The retry is bounded (1 attempt) to prevent spawn loops.

## 3. Baseline data (collected 2026-08-15T23:24-23:29Z)

- 10 attempts, 30s interval, fresh `gh auth token` each attempt
- Result: **10 / 10 SUCCESS** (100% success rate)
- Token length: 42 bytes (consistent across all attempts)
- No TLS errors, no 400, no `bad credentials`

See `OCULUS_v1_0_2_BASELINE.md` for full probe log.

## 4. Baseline outcome

**Flakiness NOT REPRODUCED in 10-attempt burst (5-min window).**

The proposed v1.0.2 fix (`gh auth refresh` retry hook in heartbeat.ps1) **lacks empirical motivation** under current host conditions (token cached, network reachable, gh auth valid).

## 5. Withdrawal rationale

Per SELF_UPDATE_PROTOCOL step 7 ("принять как CANDIDATE") — CANDIDATE requires an acceptable failure rate that justifies the change. None was observed. The proposal did not advance to CANDIDATE.

The user's earlier report of "Heartbeat-loop GitHub push flakiness" was either:
- (a) A transient window that has self-resolved (token refresh, network recovery),
- (b) Specific to a different process state (e.g., expired gh auth cached credential),
- (c) Outside of this host's current state.

## 6. Decision

**PROPOSAL WITHDRAWN.** OCULUS v1.0.1 remains canonical. No v1.0.2 patch is needed.

## 7. Next steps

- If flakiness is observed again in future, re-run this probe at that time. Pattern: `C:\Windows\Temp\gh_push_probe.ps1` (10 attempts × 30s).
- If failure rate > 0%, re-open PROPOSAL-OCULUS-2026-08-15-V1.0.2-HEARTBEAT-PUSH and apply the auth-refresh retry hook.
- Reference: see `OCULUS_v1_0_2_BASELINE.md` for original baseline data.

## 8. References

- MEMORY.md line 81 ("Heartbeat-loop GitHub push flakiness")
- MEMORY.md line 67 ("gh api PUT 400 / Invalid request recovery pattern")
- MEMORY.md line 82 ("DISCOSURE-AS-2-STEP for USER OVERRIDE publication")
- v1.0.1 patch layer (5 files): MEMORY-oculus-v1-0-1.md §A
- SELF_UPDATE_PROTOCOL.md (steps 1-10)
- OCULUS_v1_0_2_BASELINE.md (collected baseline data)
- `C:\Windows\Temp\gh_push_probe.ps1` (probe script, reusable)
- `C:\Windows\Temp\gh_push_probe_log.txt` (probe log, 10 lines)
