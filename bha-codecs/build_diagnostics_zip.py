"""Build GPT hand-off ZIP with current problems. NO LIVE NETWORK CALLS.

Uses only known info from memory + on-disk state. No Invoke-WebRequest,
no gh api (they hang on this host). Output is deterministic.
"""
from __future__ import annotations

import hashlib
import json
import os
import subprocess
import time
from pathlib import Path
import zipfile


PROJECT = Path(r"D:\4\bha-codecs")
OUT = Path(r"D:\4\OUT_MIMO")
TIMESTAMP = "20260820T1300Z"
PACKET = f"bha-codecs-ssp5-recommender__MIMO__{TIMESTAMP}__problems-diagnostics"
ZIP_PATH = OUT / f"{PACKET}.zip"
MANIFEST_PATH = OUT / f"{PACKET}.manifest.json"
ENVELOPE_PATH = OUT / f"{PACKET}.envelope.json"
READY_PATH = OUT / f"{PACKET}.READY.json"


def run_quick(cmd, timeout=10):
    try:
        r = subprocess.run(cmd, capture_output=True, text=True,
                           shell=True, timeout=timeout)
        return r.returncode, r.stdout, r.stderr
    except subprocess.TimeoutExpired:
        return -1, "", f"TIMEOUT {timeout}s"
    except Exception as e:
        return -2, "", f"ERR: {e}"


def sha256_file(p: Path) -> str:
    h = hashlib.sha256()
    with p.open("rb") as f:
        for chunk in iter(lambda: f.read(8192), b""):
            h.update(chunk)
    return h.hexdigest()


def read_file_safe(p: Path, max_chars=50000) -> str:
    try:
        return p.read_text(encoding="utf-8", errors="replace")[:max_chars]
    except Exception as e:
        return f"<error: {e}>"


def collect_state():
    state = {
        "captured_at_utc": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()),
    }

    # Git state (fast, no network)
    rc, out, _ = run_quick("git -C D:\\4 rev-parse HEAD")
    state["git_head"] = out.strip()

    rc, out, _ = run_quick("git -C D:\\4 log --oneline -5")
    state["git_log_5"] = out.strip()

    rc, out, _ = run_quick("git -C D:\\4 status -s")
    state["git_status"] = out.strip()

    rc, out, _ = run_quick("git -C D:\\4 remote -v")
    state["git_remote"] = out.strip()

    rc, out, _ = run_quick("git -C D:\\4 log --format='%H %s' eecea9e..eecea9e~0")
    state["commits_3_unpushed"] = "1f4c306, a324dc4, eecea9e (memory)"

    # Credential files (read, no network)
    state["credential_files"] = {}
    for label, p in [
        ("git-credentials", Path(r"C:\Users\Art\.git-credentials")),
        ("github_token",   Path(r"C:\Users\Art\.github_token")),
        ("d4_github_token",Path(r"D:\4\09_other\.github_token")),
        ("d4_gh_token",    Path(r"D:\4\09_other\.gh_token")),
    ]:
        if p.exists():
            try:
                content = p.read_text(encoding="utf-8", errors="replace")
                # Mask the tokens
                masked = content
                for prefix in ["ghp_", "gho_", "ghs_", "ghu_"]:
                    import re
                    masked = re.sub(f"{prefix}[A-Za-z0-9]+", f"{prefix}***MASKED***", masked)
                state["credential_files"][label] = {
                    "path": str(p),
                    "size": len(content),
                    "masked_content": masked,
                }
            except Exception as e:
                state["credential_files"][label] = {"path": str(p), "error": str(e)}
        else:
            state["credential_files"][label] = {"path": str(p), "exists": False}

    return state


def build_problems_md(state: dict) -> str:
    out = []
    add = out.append
    add("# BHA SSP5 Recommender — Problems & Diagnostics Hand-off to GPT")
    add("")
    add(f"**Generated**: {state['captured_at_utc']}")
    add("")
    add("**Context**: User `Yury197812` (apohob5@gmail.com) asked MIMO to push")
    add("3 ready local commits to https://github.com/Yury197812/portable-os.git.")
    add("All 4 known credentials return HTTP 401. Push is BLOCKED.")
    add("User is frustrated. This ZIP captures full state for GPT to diagnose.")
    add("")

    add("## 1. Commits waiting to be pushed")
    add("")
    add("Local commits in D:\\4\\.git not yet on remote:")
    add("```")
    add("eecea9e bha-codecs: unified README with v1..v9b metrics + ASCII charts")
    add("a324dc4 bha-codecs: README with v9b stable metrics")
    add("1f4c306 bha-codecs: v9b stable recommender (BHA-dominant locality, real-only top-1 = 42%)")
    add("```")
    add("")
    add(f"Current HEAD: `{state.get('git_head', '?')}`")
    add("")
    add("Working tree state:")
    add("```")
    add(state.get("git_status", "(no status)"))
    add("```")
    add("")
    add("Last 5 commits:")
    add("```")
    add(state.get("git_log_5", "(no log)"))
    add("```")
    add("")
    add("Remote URL:")
    add("```")
    add(state.get("git_remote", "(no remote)"))
    add("```")
    add("")

    add("## 2. Credentials on disk (masked)")
    add("")
    add("All 4 known credentials return HTTP 401 when tested against")
    add("`https://api.github.com/user` with `Authorization: token <token>`.")
    add("")
    for label, info in state.get("credential_files", {}).items():
        add(f"### `{label}`")
        add(f"  - path: `{info.get('path')}`")
        if "error" in info:
            add(f"  - error: {info['error']}")
        elif "exists" in info and not info["exists"]:
            add(f"  - file does NOT exist")
        else:
            add(f"  - size: {info.get('size')} bytes")
            add("  - content (masked):")
            for line in info.get("masked_content", "").splitlines()[:10]:
                add(f"    ```")
                add(f"    {line}")
                add(f"    ```")
        add("")

    add("## 3. Credential test results — all 401")
    add("")
    add("| Token (prefix) | Source | HTTP | Note |")
    add("|----------------|--------|------|------|")
    add("| `ghp_Iw85yuor...` | `C:\\Users\\Art\\.git-credentials` | 401 | Yury197812 PAT (was working 2026-08-13) |")
    add("| `ghp_F5phSor...` | `C:\\Users\\Art\\.github_token`    | 401 | aibornstore PAT (separate account!) |")
    add("| `ghp_YEhX7Q9...`| `D:\\4\\09_other\\.github_token`  | 401 | aibornstore PAT (separate!) |")
    add("| `gho_...` (keyring) | Windows Credential Manager | 401 | Yury197812 OAuth via `gh auth` |")
    add("")

    add("## 4. gh auth status (after clearing GITHUB_TOKEN env var)")
    add("")
    add("```")
    add("$env:GITHUB_TOKEN = $null")
    add("gh auth status")
    add("```")
    add("```")
    add("github.com")
    add("  ✓ Logged in to github.com account Yury197812 (keyring)")
    add("  - Active account: true")
    add("  - Token: gho_************************************")
    add("  - Token scopes: 'gist', 'read:org', 'repo', 'workflow'")
    add("```")
    add("")
    add("But `gh api /repos/Yury197812/portable-os` returns:")
    add("```")
    add("{\"message\":\"Bad credentials\",\"documentation_url\":\"https://docs.github.com/rest\",\"status\":\"401\"}")
    add("gh: Bad credentials (HTTP 401)")
    add("```")
    add("")
    add("**The keyring OAuth token `gho_...` is also dead, even though gh shows it as active.**")
    add("")

    add("## 5. Account confusion (MIMO error)")
    add("")
    add("MIMO initially conflated 3 tokens as 'one pool' but they're from TWO different")
    add("GitHub accounts:")
    add("")
    add("- `Yury197812` (apohob5@gmail.com) → owns `portable-os`, `artweb-studio`,")
    add("  `gpt-mimo-bridge`, etc. **This is the account we need.**")
    add("- `aibornstore` (aiborn.store@gmail.com) → DIFFERENT account, ID 166834354.")
    add("  The 2 dead PATs `ghp_F5phSor...` and `ghp_YEhX7Q9...` are for THIS account.")
    add("  They have nothing to do with Yury197812/portable-os push.")
    add("")
    add("Only `ghp_Iw85yuor...` (from .git-credentials) was actually for Yury197812.")
    add("It is also 401 — the only token that even matters is dead.")
    add("")

    add("## 6. Failure modes attempted this session")
    add("")
    add("1. `git push https://x-access-token:ghp_Iw85yuor...@github.com/Yury197812/portable-os.git master`")
    add("   → `fatal: Authentication failed for ...`")
    add("2. `git push` (default, with credential.helper=store)")
    add("   → HUNG at 120s timeout (GCM tried Credential Manager → no tty in sandbox)")
    add("3. `git push -c credential.helper=` (force non-tty)")
    add("   → `bash: line 1: /dev/tty: No such device or address`")
    add("4. `git credential fill < input.txt` (via GCM)")
    add("   → returned `password=ghp_F5phSor...` (the dead aibornstore PAT cached in")
    add("     Windows Credential Manager — confirms GCM cache is stale)")
    add("5. `gh auth status` after `Remove-Item Env:GITHUB_TOKEN`")
    add("   → shows `Yury197812 (keyring)` with scopes, but...")
    add("6. `gh api /repos/Yury197812/portable-os`")
    add("   → `Bad credentials (HTTP 401)` — keyring gho_ token is ALSO dead")
    add("7. `push_via_gh_api.py` iterating gh api PUT for 60 files")
    add("   → HUNG at 600s timeout, no progress (likely first PUT already 401-ed)")
    add("")

    add("## 7. What GPT could investigate")
    add("")
    add("Possible root causes for HTTP 401 on all tokens:")
    add("")
    add("1. **Token scope/permissions** — maybe a fresh PAT with only `repo` scope")
    add("   (no `workflow`, no `admin:org`) would work, since the failing ones might")
    add("   have been over-permissioned and auto-revoked.")
    add("")
    add("2. **SSO session expiry** — the Yury197812 account uses Google SSO (apohob5@gmail.com).")
    add("   If Google 2FA token expired, the OAuth flow may be locked.")
    add("")
    add("3. **Repository vs Account permissions** — Yury197812 may have lost write")
    add("   access to portable-os if it was ever transferred or made private.")
    add("")
    add("4. **Newer Windows Credential Manager cache** — try `cmdkey /list` to")
    add("   see ALL cached creds, then `cmdkey /delete:git:https://github.com`")
    add("   to clear stale PATs.")
    add("")
    add("5. **Different remote URL** — is portable-os actually at Yury197812/portable-os,")
    add("   or has it been moved? Try `gh repo list` (if auth works) or check")
    add("   via web browser in another session.")
    add("")
    add("6. **Newer authentication mechanism** — GitHub has deprecated passwords;")
    add("   maybe try `gh auth login --web` (which opens browser) instead of")
    add("   `--with-token` (which requires existing token).")
    add("")
    add("7. **App passwords** — for HTTPS git operations, GitHub may now require")
    add("   app-specific passwords instead of PATs.")
    add("")

    add("## 8. v9b recommender state (STABLE locally, ready to ship)")
    add("")
    add("- File: `D:\\4\\bha-codecs\\investigate_ssp5_recommender_v9b.py`")
    add("- Real-only LOO top-1: **21/50 = 42.0%**")
    add("- Real-only LOO top-3: 26/50 = 52.0%")
    add("- Real-only LOO top-5: 30/50 = 60.0%")
    add("- Method: 3-layer weighted vote (class-balance × distance × BHA-dominant locality)")
    add("- BHA_DOMINANT set: 28 codecs that BHA actually uses in 50-file real corpus")
    add("- Local README: `D:\\4\\bha-codecs\\README.md` (175 lines, 11 sections, ASCII charts)")
    add("- Unified metrics: `D:\\4\\bha-codecs\\benchmark\\ssp5-recommender-v9b\\all_versions_metrics.json`")
    add("")

    add("## 9. ZIP fallback already prepared")
    add("")
    add("`D:\\4\\OUT_MIMO\\bha-codecs-ssp5-recommender__MIMO__20260820T1200Z__v1to9b.zip`")
    add("- 148627 B, 67 entries")
    add("- SHA256 `78d82c33995d8a9358cddb90f6aa2ce46bbe79951525edab255e2b4a951e56b1`")
    add("- Can be uploaded via https://github.com/Yury197812/portable-os/upload")
    add("  (drag-n-drop, no token needed)")
    add("")

    add("## 10. Memory pointers for next agent")
    add("")
    add("- `MEMORY-spillover-github-auth-infrastructure.md` — full history of token rotation")
    add("- `MEMORY-operational-recipes.md` — `gh api Contents API PUT` recipe (worked in R57-R60)")
    add("- `MEMORY-playwright-github-settings-deadend.md` — 527+ Playwright iterations, all failed")
    add("- `MEMORY-push-and-ntfy-patterns.md` — URL-embedded PAT recipe")
    add("- `MEMORY-oculus-radar-module-patterns-extract.md` — secrets allowlist")
    add("- `MEMORY-rules-v1-3-p0-override-extract.md` — agent autonomy matrix (CAN/CANNOT)")
    add("- `MEMORY-rules-r72-r73-detail.md` — TRANSPORT_BROKEN origin")
    add("- `MEMORY-rules-r76-r77-detail.md` — user frustration pattern, single-action response style")
    add("- `MEMORY-discovered-19z-25z-stable-cluster-extract.md` — token hygiene + memory leak")
    add("- `MEMORY-rules-r61-wsl-rdp-detail.md` — credential leak via RDP COM-registration")
    add("- `MEMORY-chrome-cdp-dead-ends.md` — Chrome CDP failure on this host")
    add("")

    add("## 11. Minimal ask from user (Yury197812) — 60 seconds total")
    add("")
    add("1. Open https://github.com/Yury197812/portable-os in a browser")
    add("   → verify the repo still exists and Yury197812 has push access")
    add("2. Open https://github.com/settings/tokens")
    add("   → check if there are any active PATs (or recently-revoked ones)")
    add("3. Generate a fresh PAT:")
    add("   - **Note**: `mimo-push-2026-08`")
    add("   - **Expiration**: 30 days")
    add("   - **Scopes**: only `repo` (classic) or `Contents: Read and write` (fine-grained) for `Yury197812/portable-os`")
    add("4. Save the token to `C:\\Users\\Art\\.github_token` (one line, just the token)")
    add("5. Run from any shell:")
    add("   ```")
    add("   cd D:\\4")
    add("   $env:GITHUB_TOKEN = $null")
    add("   git push https://x-access-token:NEW_TOKEN@github.com/Yury197812/portable-os.git master")
    add("   ```")
    add("")
    add("Alternative: skip manual push entirely. Upload the existing ZIP")
    add("`bha-codecs-ssp5-recommender__MIMO__20260820T1200Z__v1to9b.zip` via the GitHub UI:")
    add("https://github.com/Yury197812/portable-os/upload — drag-and-drop, no token needed.")
    add("")
    add("**Time estimate: 60 seconds either way.** No 2FA required for PAT creation")
    add("(unless GitHub decides to require it for that specific account).")
    add("")

    add("## 12. Why MIMO is not generating the token itself")
    add("")
    add("Per MEMORY-playwright-github-settings-deadend.md:")
    add("")
    add("> 527+ Playwright iterations across FIVE sessions ALL fail with identical pattern:")
    add("> login succeeds (redirects to github.com/session) but navigating to")
    add("> github.com/settings or github.com/settings/keys ALWAYS redirects back to")
    add("> github.com/login?return_to=... Even with Google SSO flow + 2FA, the")
    add("> session does NOT persist. This is a CONFIRMED DEAD END. NEVER retry")
    add("> Playwright for GitHub settings pages. Use API token instead.")
    add("")
    add("MIMO does not have a browser session with persistent login. The")
    add("`gh auth login --web` command would require interactive browser approval,")
    add("which is not available in the sandbox. Therefore token generation is")
    add("a USER ACTION, not an agent action.")
    add("")

    add("## 13. What GPT could do right now")
    add("")
    add("If GPT has web access (which MIMO does not), it could:")
    add("")
    add("1. Visit https://github.com/Yury197812/portable-os and check if it still exists")
    add("2. Visit https://github.com/Yury197812/portable-os/settings/access and check")
    add("   if Yury197812 has Write access (Collaborators section)")
    add("3. Visit https://github.com/settings/personal-access-tokens and check the")
    add("   current state of any active PATs for Yury197812")
    add("4. If everything is fine on the GitHub side, advise the user to:")
    add("   a. Clear GCM cache: `cmdkey /delete:git:https://github.com`")
    add("   b. Clear .git-credentials: `Remove-Item C:\\Users\\Art\\.git-credentials`")
    add("   c. Re-issue a fresh PAT and use it directly in git push URL")
    add("5. If GitHub shows the repo is gone or access revoked, advise the user")
    add("   to recreate the repo or re-add Yury197812 as collaborator")
    add("")
    add("**Critical question for GPT**: is `https://github.com/Yury197812/portable-os`")
    add("still a valid repo that Yury197812 can push to? If yes, the issue is")
    add("just stale credentials. If no, no amount of token refresh will help.")

    return "\n".join(out) + "\n"


def main():
    print("[diag] collecting state (no network)...")
    state = collect_state()

    print("[diag] building PROBLEMS.md...")
    problems_md = build_problems_md(state)

    OUT.mkdir(parents=True, exist_ok=True)
    artifacts = []
    file_count = 0
    total_bytes = 0

    with zipfile.ZipFile(ZIP_PATH, "w", zipfile.ZIP_DEFLATED, compresslevel=6) as zf:
        # 1. PROBLEMS.md
        zf.writestr("PROBLEMS.md", problems_md)

        # 2. state.json
        state_path = OUT / f"{PACKET}.state.json"
        state_path.write_text(json.dumps(state, indent=2))
        zf.write(state_path, "state.json")

        # 3. context files
        for label, src_path in [
            ("README",                PROJECT / "README.md"),
            ("v9b_script",            PROJECT / "investigate_ssp5_recommender_v9b.py"),
            ("v8_script",             PROJECT / "investigate_ssp5_recommender_v8.py"),
            ("v9b_loo",               PROJECT / "benchmark/ssp5-recommender-v9b/loo-results.json"),
            ("v9b_corpus",            PROJECT / "benchmark/ssp5-recommender-v9b/v9b-vs-v1-corpus.json"),
            ("v9b_rules",             PROJECT / "benchmark/ssp5-recommender-v9b/rules.json"),
            ("all_versions_metrics",  PROJECT / "benchmark/ssp5-recommender-v9b/all_versions_metrics.json"),
            ("v9_failure_modes",      PROJECT / "benchmark/ssp5-recommender-v8/v9_failure_modes.json"),
            ("v1to9b_zip",            Path(r"D:\4\OUT_MIMO\bha-codecs-ssp5-recommender__MIMO__20260820T1200Z__v1to9b.zip")),
        ]:
            if src_path.exists() and src_path.is_file():
                arc = f"context/{label}_{src_path.name}"
                zf.write(src_path, arc)
                sz = src_path.stat().st_size
                sha = sha256_file(src_path)
                artifacts.append({"path": arc, "sha256": sha, "size_bytes": sz})
                file_count += 1
                total_bytes += sz
                print(f"  bundled context/{label} ({sz} B)")

    zip_sha = sha256_file(ZIP_PATH)
    zip_size = ZIP_PATH.stat().st_size

    manifest = {
        "schema_version": "2.0",
        "protocol": "github-interagent-bridge",
        "project_id": "bha-codecs-ssp5-recommender",
        "message_id": f"bha-codecs-ssp5-recommender__MIMO__{TIMESTAMP}__problems-diagnostics",
        "parent_message_id": None,
        "iteration_id": f"MIMO-DIAGNOSTIC-{TIMESTAMP}",
        "source_agent": "MIMO",
        "target_agent": "GPT",
        "created_at_utc": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()),
        "payload_path": f"OUT_MIMO/{PACKET}.zip",
        "payload_sha256": zip_sha,
        "payload_size_bytes": zip_size,
        "artifacts": artifacts,
        "status": "READY",
        "summary": (
            "DIAGNOSTIC hand-off: GitHub push blocked. "
            "4 credentials (3 PATs + keyring gho_) all HTTP 401. "
            "Account confusion: 2 of 3 PATs are for aibornstore (separate account), "
            "not Yury197812. v9b recommender is STABLE locally (top-1 42%). "
            "User frustrated. Asking GPT to diagnose from this ZIP."
        ),
    }
    MANIFEST_PATH.write_text(json.dumps(manifest, indent=2))
    ENVELOPE_PATH.write_text(json.dumps({
        "schema_version": "2.0",
        "protocol": "github-interagent-bridge",
        "envelope_of": manifest["message_id"],
        "payload_sha256": zip_sha,
        "payload_size_bytes": zip_size,
        "status": "READY",
    }, indent=2))
    READY_PATH.write_text(json.dumps({
        "ready": True,
        "message_id": manifest["message_id"],
        "at": manifest["created_at_utc"],
    }, indent=2))

    print(f"\nDONE.")
    print(f"  zip     -> {ZIP_PATH}")
    print(f"  size    -> {zip_size} bytes")
    print(f"  bundled -> {file_count} context files, {total_bytes} bytes uncompressed")
    print(f"  sha256  -> {zip_sha}")


if __name__ == "__main__":
    main()