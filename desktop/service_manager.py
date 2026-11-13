from __future__ import annotations

import ctypes
import json
import os
import subprocess
import time
import urllib.error
import urllib.request
from pathlib import Path

from desktop.runtime_paths import (
    API_PORT,
    DATABASE_URL,
    WEB_PORT,
    RuntimePaths,
)


DETACHED_PROCESS = 0x00000008
CREATE_NEW_PROCESS_GROUP = 0x00000200
CREATE_NO_WINDOW = 0x08000000
PROCESS_FLAGS = (
    DETACHED_PROCESS | CREATE_NEW_PROCESS_GROUP | CREATE_NO_WINDOW
)


def _pid_path(paths: RuntimePaths, service: str) -> Path:
    return paths.runtime / f"{service}.pid"


def write_pid(paths: RuntimePaths, service: str, pid: int) -> None:
    paths.runtime.mkdir(parents=True, exist_ok=True)
    _pid_path(paths, service).write_text(str(pid), encoding="ascii")


def read_pid(paths: RuntimePaths, service: str) -> int | None:
    path = _pid_path(paths, service)
    try:
        return int(path.read_text(encoding="ascii").strip())
    except (FileNotFoundError, ValueError):
        return None


def process_alive(pid: int) -> bool:
    if os.name != "nt":
        try:
            os.kill(pid, 0)
            return True
        except OSError:
            return False
    process = ctypes.windll.kernel32.OpenProcess(0x1000, False, pid)
    if not process:
        return False
    try:
        exit_code = ctypes.c_ulong()
        if not ctypes.windll.kernel32.GetExitCodeProcess(
            process,
            ctypes.byref(exit_code),
        ):
            return False
        return exit_code.value == 259
    finally:
        ctypes.windll.kernel32.CloseHandle(process)


def http_ready(url: str, *, timeout: float = 1.0) -> bool:
    try:
        with urllib.request.urlopen(url, timeout=timeout) as response:
            return 200 <= response.status < 300
    except (OSError, urllib.error.URLError):
        return False


def wait_http(url: str, *, seconds: float = 45.0) -> bool:
    deadline = time.monotonic() + seconds
    while time.monotonic() < deadline:
        if http_ready(url):
            return True
        time.sleep(0.4)
    return False


def _process_env(paths: RuntimePaths) -> dict[str, str]:
    environment = os.environ.copy()
    environment["DATABASE_URL"] = DATABASE_URL
    environment["PYTHONUTF8"] = "1"
    environment["PYTHONPATH"] = str(paths.app_root)
    environment["WEAKNESS_ANALYSIS_DISABLED"] = environment.get(
        "WEAKNESS_ANALYSIS_DISABLED",
        "0",
    )
    return environment


def _start_detached(
    paths: RuntimePaths,
    service: str,
    command: list[str | Path],
) -> int:
    paths.logs.mkdir(parents=True, exist_ok=True)
    log_path = paths.logs / f"{service}.log"
    with log_path.open("ab") as log:
        process = subprocess.Popen(
            [str(item) for item in command],
            cwd=paths.app_root,
            env=_process_env(paths),
            stdin=subprocess.DEVNULL,
            stdout=log,
            stderr=subprocess.STDOUT,
            creationflags=PROCESS_FLAGS,
            close_fds=True,
        )
    write_pid(paths, service, process.pid)
    return process.pid


def start_services(paths: RuntimePaths) -> dict:
    api_url = f"http://127.0.0.1:{API_PORT}/api/v1/healthz"
    web_url = f"http://127.0.0.1:{WEB_PORT}/"
    if not http_ready(api_url):
        _start_detached(
            paths,
            "backend",
            [
                paths.python_exe,
                "-m",
                "uvicorn",
                "backend.app.main:app",
                "--host",
                "0.0.0.0",
                "--port",
                str(API_PORT),
            ],
        )
        if not wait_http(api_url):
            raise RuntimeError("BACKEND_START_FAILED")
    if not http_ready(web_url):
        _start_detached(
            paths,
            "web",
            [
                paths.python_exe,
                paths.app_root / "desktop" / "static_server.py",
                "--root",
                paths.web_root,
                "--host",
                "127.0.0.1",
                "--port",
                str(WEB_PORT),
            ],
        )
        if not wait_http(web_url):
            raise RuntimeError("WEB_START_FAILED")
    return {
        "api_url": api_url,
        "web_url": web_url,
        "backend_pid": read_pid(paths, "backend"),
        "web_pid": read_pid(paths, "web"),
    }


def _terminate_pid(pid: int) -> None:
    if not process_alive(pid):
        return
    subprocess.run(
        ["taskkill.exe", "/PID", str(pid), "/T"],
        stdout=subprocess.DEVNULL,
        stderr=subprocess.DEVNULL,
        creationflags=CREATE_NO_WINDOW,
        check=False,
    )
    deadline = time.monotonic() + 8
    while time.monotonic() < deadline and process_alive(pid):
        time.sleep(0.2)
    if process_alive(pid):
        subprocess.run(
            ["taskkill.exe", "/PID", str(pid), "/T", "/F"],
            stdout=subprocess.DEVNULL,
            stderr=subprocess.DEVNULL,
            creationflags=CREATE_NO_WINDOW,
            check=False,
        )


def stop_services(paths: RuntimePaths) -> dict:
    stopped = []
    for service in ("web", "backend"):
        pid = read_pid(paths, service)
        if pid:
            _terminate_pid(pid)
            stopped.append(service)
        try:
            _pid_path(paths, service).unlink()
        except FileNotFoundError:
            pass
    if (paths.pgdata / "PG_VERSION").is_file():
        subprocess.run(
            [
                str(paths.pgsql_exe("pg_ctl.exe")),
                "-D",
                str(paths.pgdata),
                "-m",
                "fast",
                "-w",
                "-t",
                "30",
                "stop",
            ],
            cwd=paths.app_root,
            stdout=subprocess.DEVNULL,
            stderr=subprocess.DEVNULL,
            creationflags=CREATE_NO_WINDOW,
            check=False,
        )
        stopped.append("postgres")
    return {"stopped": stopped}
