#!/usr/bin/env python3
"""Auto-restart watchdog for pl-kanban server."""
import subprocess, time, sys, urllib.request, urllib.error
from pathlib import Path

SERVER = Path(__file__).resolve().parents[0] / "server.py"
PYTHON = sys.executable
CHECK_INTERVAL = 4
PORT = "9121"
STARTUP_GRACE = 6          # seconds to wait after launch before first healthcheck
FAIL_THRESHOLD = 2         # consecutive healthcheck failures before restarting


def is_up():
    """Healthcheck using stdlib urllib (no external curl / PATH dependency)."""
    try:
        req = urllib.request.Request(f"http://127.0.0.1:{PORT}/health", method="GET")
        with urllib.request.urlopen(req, timeout=5) as resp:
            return resp.status == 200
    except Exception:
        return False


def start():
    return subprocess.Popen([PYTHON, str(SERVER)], cwd=str(SERVER.parent))


def main():
    print(f"[Watchdog] Watching {SERVER}")
    proc = start()
    print(f"[Watchdog] PID: {proc.pid}")
    print(f"[Watchdog] Grace period {STARTUP_GRACE}s before first healthcheck")
    time.sleep(STARTUP_GRACE)
    fails = 0
    while True:
        time.sleep(CHECK_INTERVAL)
        if proc.poll() is not None:
            print("[Watchdog] Server down, restarting...")
            proc = start()
            print(f"[Watchdog] Restarted PID: {proc.pid}")
            fails = 0
            time.sleep(STARTUP_GRACE)
            continue
        if is_up():
            fails = 0
        else:
            fails += 1
            if fails >= FAIL_THRESHOLD:
                print(f"[Watchdog] Healthcheck failed {fails}x, restarting...")
                try:
                    proc.terminate()
                    proc.wait(timeout=5)
                except Exception:
                    pass
                proc = start()
                print(f"[Watchdog] Restarted PID: {proc.pid}")
                fails = 0
                time.sleep(STARTUP_GRACE)


if __name__ == "__main__":
    main()
