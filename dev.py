"""
dev.py – start the backend AND the frontend with one command.

    python dev.py            # backend on :8000, frontend on :5173
    python dev.py --seed     # rebuild the demo data first (python -m seed.seed_demo)

Press Ctrl+C once to stop both.  Uses only the standard library.
Prerequisites (one time): backend venv + `pip install -r requirements.txt`, and `npm install` in
frontend/ (this script runs `npm install` for you if node_modules is missing).
"""

import os
import signal
import subprocess
import sys
import threading
import time
from pathlib import Path

ROOT = Path(__file__).resolve().parent
BACKEND = ROOT / "backend"
FRONTEND = ROOT / "frontend"
IS_WINDOWS = os.name == "nt"

COLORS = {"backend": "\033[36m", "frontend": "\033[35m", "dev": "\033[33m"}
RESET = "\033[0m"


def log(tag: str, text: str) -> None:
    print(f"{COLORS.get(tag, '')}[{tag}]{RESET} {text}", flush=True)


def backend_python() -> str:
    """The backend's own virtualenv if it exists, otherwise the Python running this script."""
    for rel in ("venv/Scripts/python.exe", "venv/bin/python", ".venv/Scripts/python.exe", ".venv/bin/python"):
        p = BACKEND / rel
        if p.exists():
            return str(p)
    return sys.executable


def npm() -> str:
    return "npm.cmd" if IS_WINDOWS else "npm"


def pump(tag: str, proc: subprocess.Popen) -> None:
    """Copy a child's output to our console with a coloured [tag] prefix."""
    for line in iter(proc.stdout.readline, ""):
        log(tag, line.rstrip())


def start(tag: str, cmd: list[str], cwd: Path) -> subprocess.Popen:
    kwargs = {}
    if IS_WINDOWS:
        kwargs["creationflags"] = subprocess.CREATE_NEW_PROCESS_GROUP   # so we can kill the whole tree
    proc = subprocess.Popen(
        cmd, cwd=cwd, stdout=subprocess.PIPE, stderr=subprocess.STDOUT,
        text=True, encoding="utf-8", errors="replace", **kwargs,
    )
    threading.Thread(target=pump, args=(tag, proc), daemon=True).start()
    return proc


def stop(proc: subprocess.Popen) -> None:
    if proc.poll() is not None:
        return
    if IS_WINDOWS:
        # /T = also kill children (uvicorn reloader workers, node processes)
        subprocess.run(["taskkill", "/F", "/T", "/PID", str(proc.pid)], capture_output=True)
    else:
        proc.terminate()
        try:
            proc.wait(timeout=5)
        except subprocess.TimeoutExpired:
            proc.kill()


def main() -> int:
    args = sys.argv[1:]
    py = backend_python()

    if not (BACKEND / ".env").exists():
        log("dev", "backend/.env not found - copy backend/.env.example to backend/.env first (AI features need the keys).")
    if not (FRONTEND / "node_modules").exists():
        log("dev", "frontend/node_modules missing - running `npm install` (first time only)...")
        if subprocess.run([npm(), "install"], cwd=FRONTEND).returncode != 0:
            log("dev", "npm install failed.")
            return 1
    if "--seed" in args:
        log("dev", "rebuilding demo data...")
        if subprocess.run([py, "-m", "seed.seed_demo"], cwd=BACKEND).returncode != 0:
            log("dev", "seeding failed.")
            return 1

    procs = {
        "backend": start("backend", [py, "-m", "uvicorn", "app.main:app", "--reload", "--port", "8000"], BACKEND),
        "frontend": start("frontend", [npm(), "run", "dev", "--", "--port", "5173"], FRONTEND),
    }

    def shutdown(*_):
        raise KeyboardInterrupt

    signal.signal(signal.SIGINT, shutdown)
    signal.signal(signal.SIGTERM, shutdown)
    if hasattr(signal, "SIGBREAK"):
        signal.signal(signal.SIGBREAK, shutdown)

    log("dev", "backend  -> http://localhost:8000  (docs: /docs)")
    log("dev", "frontend -> http://localhost:5173   (Ctrl+C stops both)")
    code = 0
    try:
        while True:
            for tag, proc in procs.items():
                if proc.poll() is not None:
                    log("dev", f"{tag} exited with code {proc.returncode}; stopping the other one.")
                    code = proc.returncode or 1
                    raise KeyboardInterrupt
            time.sleep(0.5)
    except KeyboardInterrupt:
        pass
    finally:
        log("dev", "stopping...")
        for proc in procs.values():
            stop(proc)
        log("dev", "stopped.")
    return code


if __name__ == "__main__":
    sys.exit(main())
