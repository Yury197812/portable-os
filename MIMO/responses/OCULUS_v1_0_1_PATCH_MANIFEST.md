OCULUS v1.0.1 PATCH MANIFEST

Source: o:\3\OCULUS_UNIVERSAL_PROJECT_OS_V1_0_0_20260815.zip (canonical filename, 86982 bytes, sha256 F6A0E8242E59F45BE15EEF9101765A20AE32DA25A17BB5BE667E029AF25F9974)
Generated: 2026-08-15T22:09Z
Generator: agent (USER OVERRIDE #6)
Files changed between v1.0.0 and v1.0.1:

1. ORCHESTRATION/WORKER_LIFECYCLE.md
   action: appended section after existing line 23
   new_content: 4-step USER OVERRIDE protocol (override statement required, prior disclosure, commit-message identifies WORKER_A, linked override doc)
   bytes_added: approx 600

2. SECURITY/SECURITY_TOOL_POLICY.md
   action: appended section after existing line 15
   new_content: gh api push recipe (Remove-Item Env:GITHUB_TOKEN, manual JSON, no BOM, short content, get existing SHA first)
   bytes_added: approx 1100

3. TOOLS/generate_manifest.py
   action: edited
   changes: replaced `if p.name not in {"MANIFEST.json","SHA256SUMS.txt"}:` with explicit `SELF_REFERENTIAL = {"MANIFEST.json", "SHA256SUMS.txt"}` constant + comment
   bytes_added: approx 250

4. 02_PASTE_INTO_PROJECT_INSTRUCTIONS.txt
   action: appended section after existing line 64
   new_content: KANONICAL REPLACE PATTERN (WinFsp.Np promote sequence: validate, remove OLD, move NEW to canonical, rename SHA256SUMS)
   bytes_added: approx 700

5. CHANGELOG.md
   action: prepended v1.0.1 entry
   new_content: CHANGELOG header for v1.0.1 with bullet list of changes and link to v1.0.0 entry
   bytes_added: approx 250

6. VERSION.json
   action: edited
   changes: version 1.0.0 -> 1.0.1, added previous_version: "1.0.0", patch_summary field
   bytes_added: approx 200

Total: 6 files modified, 1 patch v1.0.1 (no new files added to OCULUS itself; v1.0.1 was promoted INTO the canonical filename, replacing v1.0.0 build).

Manifest regenerated: MANIFEST.json (54 file entries, regenerated via TOOLS/generate_manifest.py)
SHA256SUMS.txt: regenerated (55 lines, includes outer-archive fingerprint extra row)

How to verify locally:
  1. sha256('o:\3\OCULUS_UNIVERSAL_PROJECT_OS_V1_0_0_20260815.zip') must = F6A0E8242E59F45BE15EEF9101765A20AE32DA25A17BB5BE667E029AF25F9974
  2. Count lines in SHA256SUMS.txt: must = 55
  3. Run `python o:\3\_oculus_extract\OCULUS_UNIVERSAL_PROJECT_OS_V1_0_0\TOOLS\validate_package.py` -> PASS expected
  4. Run `python o:\3\_oculus_extract\OCULUS_UNIVERSAL_PROJECT_OS_V1_0_0\TOOLS\generate_manifest.py` -> regenerates MANIFEST.json + SHA256SUMS.txt from disk
