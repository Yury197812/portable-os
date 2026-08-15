# SELF_UPDATE/ — index of self-update artifacts

owner: mimocode (orchestrator)
purpose: durable index of all self-update artifacts created under OCULUS SELF_UPDATE_PROTOCOL.
status: CANONICAL — for OCULUS v1.0.1 package, regenerated when new artifacts are added.

## 1. Canonical artifacts (in `o:\3\_oculus_extract\OCULUS_UNIVERSAL_PROJECT_OS_V1_0_0\SELF_UPDATE\`)

### 1.1. `SELF_UPDATE_PROTOCOL.md` (889 b)
The protocol definition. Defines steps 1-10 of an OCULUS self-update cycle:
1. Определить baseline
2. Решить
3. Применить
4. Создать proposal
5. Провести baseline
6. Измерить
7. Негативные взаимодействия (acceptance criteria)
8. Independent review (Control Tower)
9. Migrate-acceptance
10. Release

This is the canonical reference for all self-update cycles. Each cycle should produce one of the following:
- `EXPERIMENT_<TITLE>_<DATE>.md` (cycle still in progress, no CANONICAL change)
- `PROPOSAL_<TITLE>_<DATE>.md` (proposal written, not yet CANDIDATE)
- `BASELINE_<TITLE>_<DATE>.md` (baseline data measured)
- `PATCH_<TITLE>_<DATE>.md` (CANONICAL change applied, validated)
- `DECISION_RECORD_<TITLE>_<DATE>.md` (audit of architectural decisions)

### 1.2. `EXPERIMENT_OCULUS_v1_0_2_HEARTBEAT_PUSH_2026-08-15.md` (3632 b)
Cycle: v1.0.2 heartbeat-loop GitHub push flakiness (NOT REPRODUCED).
- Date: 2026-08-15T23:24:18Z → 23:29:12Z
- Hypothesis: H1 (LF vs CRLF) OR H2 (TLS timeout on `gh auth refresh`)
- Method: 10 attempts × 30s via `C:\Windows\Temp\gh_push_probe.ps1`
- Result: **10 / 10 SUCCESS** (100% success rate, token length 42 b consistent)
- Status: BASELINE_INCONCLUSIVE — proposal did NOT advance to CANDIDATE
- See also: `OCULUS_v1_0_2_PROPOSAL.md` (status WITHDRAWN), `OCULUS_v1_0_2_BASELINE.md`

### 1.3. `PATCH_OCULUS_v1_0_1_2026-08-15.md` (6783 b)
Cycle: v1.0.1 patch layer (CANONICAL real application).
- Date: 2026-08-15T21:46Z (promote to canonical), 22:10Z (published to GitHub)
- Modified files (6): `ORCHESTRATION/WORKER_LIFECYCLE.md`, `SECURITY/SECURITY_TOOL_POLICY.md`, `TOOLS/generate_manifest.py`, `02_PASTE_INTO_PROJECT_INSTRUCTIONS.txt`, `CHANGELOG.md`, `VERSION.json`
- Plus 2 regenerations: `MANIFEST.json`, `SHA256SUMS.txt`
- Status: CANONICAL — ACCEPTed by Control Tower, MERGED to master HEAD `bdb168e2…`
- See also: `OCULUS_v1_0_1_RELEASE.md`, `OCULUS_v1_0_1_PATCH_MANIFEST.md`, `USER_OVERRIDE_V1_0_1_PUSH_TO_GITHUB.md`, `OCULUS_v1_0_1_ACCEPTED.md`, `OCULUS_v1_0_1_MERGED_TO_MASTER.md`

### 1.4. `DECISION_RECORD_SESSION_2026-08-15.md` (7871 b)
Cycle: full audit of architectural decisions made during session 2026-08-15.
- 6 decisions (D1-D6) and 5 lessons (L1-L5)
- Open followups documented
- Status: CANONICAL — for audit purposes only

## 2. Anti-patterns to avoid (durably)

- **DO NOT** create new artifacts directly in this folder without first checking that the file doesn't already exist (idempotency check).
- **DO NOT** modify `SELF_UPDATE_PROTOCOL.md` without explicit override (this is the canonical protocol definition).
- **DO NOT** push artifacts from this folder to GitHub without user override + `USER_OVERRIDE_PUSH_RESULTS_*.md` doc.
- **DO** regenerate `MANIFEST.json` and `SHA256SUMS.txt` after every artifact change (via `TOOLS\generate_manifest.py`).
- **DO** validate after every change (via `TOOLS\validate_package.py` → `OCULUS_PACKAGE_VALIDATE PASS`).
- **DO** record all artifacts under canonical filenames matching the templates.

## 3. Related artifacts (in `MIMO/responses/` on GitHub master)

These are the published sibling artifacts. They live in the GitHub repo, not in this folder:
- `OCULUS_v1_0_1_RELEASE.md` (sha `da6a5cdb…`)
- `OCULUS_v1_0_1_PATCH_MANIFEST.md` (sha `047c46cf…`)
- `USER_OVERRIDE_V1_0_1_PUSH_TO_GITHUB.md` (sha `4f024f2f…`)
- `USER_OVERRIDE_PUSH_RESULTS_V1_0_1_GITHUB.md` (sha `21fdd284…`)
- `OCULUS_v1_0_1_ACCEPTED.md` (sha `d4a7b559…`)
- `OCULUS_v1_0_1_MERGED_TO_MASTER.md` (sha `9026e060…`)
- Master HEAD: `bdb168e2097c03d2f12efcb9fa96fe2d3cbad4fc` (2026-08-15T19:43:31Z)

## 4. Filename templates

- `EXPERIMENT_<TITLE>_<YYYY-MM-DD>.md`
- `PROPOSAL_<TITLE>_<YYYY-MM-DD>.md`
- `BASELINE_<TITLE>_<YYYY-MM-DD>.md`
- `PATCH_<TITLE>_<YYYY-MM-DD>.md`
- `DECISION_RECORD_<TITLE>_<YYYY-MM-DD>.md`

All `<TITLE>` should be unique and descriptive. Avoid duplicate titles across cycles (use date suffix or version suffix when necessary).

## 5. Validation flow

After every artifact change:
```
cd o:\3\_oculus_extract\OCULUS_UNIVERSAL_PROJECT_OS_V1_0_0
python TOOLS\generate_manifest.py
python TOOLS\validate_package.py
```

Expected output:
```
manifest <N>
OCULUS_PACKAGE_VALIDATE PASS
```

If `validate_package.py` fails, **DO NOT** commit — fix the manifest issue first.

## 6. History

| Date | Artifact | Status |
|------|----------|--------|
| 2026-08-15T23:42Z | EXPERIMENT_OCULUS_v1_0_2_HEARTBEAT_PUSH_2026-08-15.md | BASELINE_INCONCLUSIVE |
| 2026-08-15T23:50Z | PATCH_OCULUS_v1_0_1_2026-08-15.md | CANONICAL |
| 2026-08-15T23:55Z | DECISION_RECORD_SESSION_2026-08-15.md | CANONICAL |
| 2026-08-16T00:00Z | README.md (this file) | CANONICAL |