package: OCULUS UNIVERSAL PROJECT OPERATING SYSTEM
version: 1.0.1
date: 2026-08-15
release_type: USER_OVERRIDE_6 (Common Patch publication)
predecessor: v1.0.0
location: o:\3\OCULUS_UNIVERSAL_PROJECT_OS_V1_0_0_20260815.zip (canonical filename, 86982 bytes, sha256 F6A0E8242E59F45BE15EEF9101765A20AE32DA25A17BB5BE667E029AF25F9974)
provenance:
  override_id: 6
  override_doc: MIMO/responses/USER_OVERRIDE_V1_0_1_PUSH_TO_GITHUB.md
  override_pointer: MIMO/responses/USER_OVERRIDE_PUSH_RESULTS_V1_0_1_GITHUB.md
  user_transcript: "Пушь v1.0.1 на GitHub" (2026-08-15T22:08Z)
  cloud_state: v1.0.1 already uploaded to Mail.ru cloud by user (drag-and-drop, 22:00Z)
  awaiting: Control Tower ACCEPT or REJECT (per USER OVERRIDE protocol line 30 step 4)

what_changed_v1_0_0_to_v1_0_1:
  - ORCHESTRATION/WORKER_LIFECYCLE.md: 4-step USER OVERRIDE protocol appended.
  - SECURITY/SECURITY_TOOL_POLICY.md: gh api push recipe appended (no BOM, clear env, short content).
  - TOOLS/generate_manifest.py: SELF_REFERENTIAL guard added (skip MANIFEST.json + SHA256SUMS.txt from own SHA computation).
  - 02_PASTE_INTO_PROJECT_INSTRUCTIONS.txt: KANONICAL REPLACE PATTERN stanza appended.
  - CHANGELOG.md: 1.0.1 entry.
  - VERSION.json: 1.0.0 -> 1.0.1, previous_version + patch_summary fields added.

how_to_validate:
  - python o:\3\_oculus_extract\OCULUS_UNIVERSAL_PROJECT_OS_V1_0_0\TOOLS\validate_package.py (PASS expected)
  - python o:\3\_oculus_extract\OCULUS_UNIVERSAL_PROJECT_OS_V1_0_0\TOOLS\generate_manifest.py (regenerates MANIFEST.json + SHA256SUMS.txt)
  - sha256(o:\3\OCULUS_UNIVERSAL_PROJECT_OS_V1_0_0_20260815.zip) must equal F6A0E8242E59F45BE15EEF9101765A20AE32DA25A17BB5BE667E029AF25F9974
  - count(o:\3\OCULUS_UNIVERSAL_PROJECT_OS_V1_0_0_20260815.SHA256SUMS.txt) must equal 55 lines
