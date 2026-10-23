"""Explicit local-only supervisor for an SSH tunnel and Uvicorn reload."""
import os
from pathlib import Path
import signal
import socket
import subprocess
import sys
import time

from app.settings import Settings, get_settings


BACKEND_DIR = Path(__file__).resolve().parents[1]


def require_free_port(host: str, port: int) -> None:
    try:
        with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as listener:
            listener.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
            listener.bind((host, port))
    except OSError as error:
        raise RuntimeError(f"Local port {host}:{port} is unavailable; close its existing owner or change the local port. No existing process was stopped.") from error


def wait_for_tunnel(process: subprocess.Popen, host: str, port: int) -> None:
    deadline = time.monotonic() + 15
    while time.monotonic() < deadline:
        if process.poll() is not None:
            raise RuntimeError("SSH tunnel failed. Check the SSH host, known-host entry, key and ssh-agent; the backend was not started.")
        try:
            with socket.create_connection((host, port), timeout=0.2):
                return
        except OSError:
            time.sleep(0.1)
    raise RuntimeError("SSH tunnel startup timed out; the backend was not started.")


def stop_process(process: subprocess.Popen | None) -> None:
    if process is None:
        return
    # Each child owns a separate group, including Uvicorn's reload worker.
    # The group can outlive its leader, so do not skip cleanup on poll().
    try:
        os.killpg(process.pid, signal.SIGTERM)
    except ProcessLookupError:
        pass
    deadline = time.monotonic() + 5
    while True:
        process.poll()  # Reap our leader while checking for surviving workers.
        try:
            os.killpg(process.pid, 0)
        except ProcessLookupError:
            break
        remaining = deadline - time.monotonic()
        if remaining <= 0:
            try:
                os.killpg(process.pid, signal.SIGKILL)
            except ProcessLookupError:
                pass
            break
        time.sleep(min(0.1, remaining))
    process.wait()


def run_dev(settings: Settings) -> int:
    if settings.app_env != "development":
        raise ValueError("The local launcher requires APP_ENV=development; it is not a production entry point.")
    if settings.db_host != "127.0.0.1":
        raise ValueError("Automatic SSH forwarding requires DB_HOST=127.0.0.1.")
    if not settings.dev_ssh_host:
        raise ValueError("Set DEV_SSH_HOST in backend/.env to the cloud address or your SSH config alias.")
    if settings.db_port == settings.dev_backend_port:
        raise ValueError("DB_PORT and DEV_BACKEND_PORT must differ.")
    require_free_port(settings.db_host, settings.db_port)
    require_free_port("127.0.0.1", settings.dev_backend_port)
    ssh = backend = None
    try:
        ssh = subprocess.Popen([
            "ssh", "-N", "-o", "BatchMode=yes", "-o", "StrictHostKeyChecking=yes",
            "-o", "ForkAfterAuthentication=no", "-o", "ControlMaster=no",
            "-o", "ControlPath=none", "-o", "ControlPersist=no",
            "-o", "ExitOnForwardFailure=yes", "-o", "ConnectTimeout=10",
            "-o", "ServerAliveInterval=30", "-o", "ServerAliveCountMax=3",
            "-p", str(settings.dev_ssh_port), "-l", settings.dev_ssh_user,
            "-L", f"127.0.0.1:{settings.db_port}:127.0.0.1:{settings.dev_db_remote_port}",
            settings.dev_ssh_host,
        ], stdin=subprocess.DEVNULL, start_new_session=True)
        wait_for_tunnel(ssh, settings.db_host, settings.db_port)
        print(f"[dev] SSH tunnel ready on 127.0.0.1:{settings.db_port}; starting backend on {settings.dev_backend_port}.", flush=True)
        backend = subprocess.Popen([
            sys.executable, "-m", "uvicorn", "app.main:app", "--reload",
            "--host", "127.0.0.1", "--port", str(settings.dev_backend_port),
        ], cwd=BACKEND_DIR, start_new_session=True)
        while True:
            status = backend.poll()
            if status is not None:
                return status
            if ssh.poll() is not None:
                raise RuntimeError("SSH tunnel disconnected; stopping the local backend. Run the local launcher again.")
            time.sleep(0.2)
    finally:
        try:
            stop_process(backend)
        finally:
            stop_process(ssh)


def main() -> int:
    def interrupted(_signum, _frame):
        raise KeyboardInterrupt

    signal.signal(signal.SIGTERM, interrupted)
    try:
        return run_dev(get_settings())
    except KeyboardInterrupt:
        print("[dev] Backend and owned SSH tunnel stopped.", flush=True)
        return 0
    except (ValueError, RuntimeError, OSError) as error:
        print(f"[dev] {error}", file=sys.stderr)
        return 1


if __name__ == "__main__":
    raise SystemExit(main())
