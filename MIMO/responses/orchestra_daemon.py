"""
orchestra_daemon.py
===================

Watchdog for the MIMO Orchestra. Keeps the four long-running services alive:

  1. ntfy bridge supervisor  (supervisor/mimo_ntfy_supervisor.py)
  2. truthful dashboard      (dashboard/dashboard_truthful.py, port 8091)
  3. ArtWeb proxy            (ArtWebStudio/artweb-studio/playground_proxy.py, port 8890)
  4. ArtWeb runtime          (ArtWebStudio/artweb-studio/runtime/runtime.py, port 8891)

Liveness signals (no process enumeration, no external deps):
  - dashboard:   HTTP GET /api/health must return 200
  - supervisor:  supervisor.log mtime must be fresh (< 120s; it logs every
                 poll tick even when auto-push is rate-limited)
  - proxy:       HTTP GET /api/health must return 200
  - runtime:     HTTP GET /api/health must return 200

Registered as a Windows scheduled task (AtLogOn + AtStartup, restart on
failure) so the whole Orchestra survives reboot and child crashes.
"""

from __future__ import annotations

import subprocess
import time
import urllib.request
from pathlib import Path

ROOT = Path(r"D:\4\OUT\MIMO")
SUP_DIR = ROOT / "supervisor"
DASH_DIR = ROOT / "dashboard"
PROXY_DIR = Path(r"C:\Users\Art\ArtWebStudio\artweb-studio")
RUNTIME_DIR = PROXY_DIR / "runtime"
LOG_PATH = ROOT / "orchestra_daemon.log"

PYW = r"C:\Program Files\Python311\pythonw.exe"
CREATE_NO_WINDOW = 0x08000000
CHECK_INTERVAL = 30          # seconds between watchdog scans
SUP_LOG_STALE = 120          # supervisor considered dead if log older than this


def log(msg: str) -> None:
    line = f"[{time.strftime('%Y-%m-%dT%H:%M:%SZ', time.gmtime())}] {msg}"
    try:
        with LOG_PATH.open("a", encoding="utf-8") as f:
            f.write(line + "\n")
    except OSError:
        pass


def spawn(args: list[str], cwd: Path) -> None:
    log(f"spawning {args[-1]} (cwd={cwd})")
    subprocess.Popen(
        [PYW, *args],
        cwd=str(cwd),
        creationflags=CREATE_NO_WINDOW,
        stdin=subprocess.DEVNULL,
        stdout=subprocess.DEVNULL,
        stderr=subprocess.DEVNULL,
    )


def dashboard_alive() -> bool:
    try:
        with urllib.request.urlopen(
            "http://localhost:8091/api/health", timeout=4
        ) as r:
            return r.status == 200
    except Exception:
        return False


def supervisor_alive() -> bool:
    try:
        age = time.time() - (SUP_DIR / "supervisor.log").stat().st_mtime
        return age < SUP_LOG_STALE
    except OSError:
        return False


def proxy_alive() -> bool:
    try:
        with urllib.request.urlopen(
            "http://127.0.0.1:8890/api/health", timeout=4
        ) as r:
            return r.status == 200
    except Exception:
        return False


def runtime_alive() -> bool:
    try:
        with urllib.request.urlopen(
            "http://127.0.0.1:8891/api/health", timeout=4
        ) as r:
            return r.status == 200
    except Exception:
        return False


def main() -> None:
    log("=== ORCHESTRA DAEMON START ===")
    while True:
        try:
            if not dashboard_alive():
                log("dashboard DOWN -> respawn")
                spawn(["dashboard_truthful.py"], DASH_DIR)
            if not supervisor_alive():
                log("supervisor DOWN -> respawn")
                spawn(["mimo_ntfy_supervisor.py"], SUP_DIR)
            if not proxy_alive():
                log("proxy DOWN -> respawn")
                spawn(["playground_proxy.py"], PROXY_DIR)
            if not runtime_alive():
                log("runtime DOWN -> respawn")
                spawn(["runtime.py", "serve"], RUNTIME_DIR)
        except Exception as e:
            log(f"scan error: {e}")
        time.sleep(CHECK_INTERVAL)


if __name__ == "__main__":
    main()
