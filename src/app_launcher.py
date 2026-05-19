from __future__ import annotations

import shutil
import socket
import subprocess
import time
import webbrowser

import uvicorn


HOST = "127.0.0.1"
PORT = 8000
APP_URL = f"http://{HOST}:{PORT}/ui/index.html"
APP_WINDOW_PROCESS: subprocess.Popen | None = None


def find_free_port(start_port: int = PORT, attempts: int = 20) -> int:
    for port in range(start_port, start_port + attempts):
        if _is_port_free(port):
            return port
    raise RuntimeError("No free local port found for JARVIS.")


def app_url(port: int = PORT) -> str:
    return f"http://{HOST}:{port}/ui/index.html"


def run_server(port: int = PORT) -> None:
    uvicorn.run("src.web_app:app", host=HOST, port=port, reload=False)


def open_app_window(url: str = APP_URL) -> None:
    global APP_WINDOW_PROCESS
    browser = _find_app_browser()
    if browser:
        APP_WINDOW_PROCESS = subprocess.Popen([browser, f"--app={url}", "--new-window"])
        return

    webbrowser.open(url)


def close_app_window() -> None:
    global APP_WINDOW_PROCESS
    if APP_WINDOW_PROCESS is None:
        return
    if APP_WINDOW_PROCESS.poll() is None:
        APP_WINDOW_PROCESS.terminate()
    APP_WINDOW_PROCESS = None


def wait_until_ready(port: int = PORT, timeout_seconds: float = 12.0) -> bool:
    deadline = time.monotonic() + timeout_seconds
    while time.monotonic() < deadline:
        try:
            with socket.create_connection((HOST, port), timeout=0.35):
                return True
        except OSError:
            time.sleep(0.2)
    return False


def _is_port_free(port: int) -> bool:
    try:
        with socket.create_connection((HOST, port), timeout=0.2):
            return False
    except OSError:
        return True


def _find_app_browser() -> str | None:
    candidates = [
        shutil.which("msedge"),
        shutil.which("chrome"),
        r"C:\Program Files (x86)\Microsoft\Edge\Application\msedge.exe",
        r"C:\Program Files\Microsoft\Edge\Application\msedge.exe",
        r"C:\Program Files\Google\Chrome\Application\chrome.exe",
        r"C:\Program Files (x86)\Google\Chrome\Application\chrome.exe",
    ]
    for candidate in candidates:
        if candidate and shutil.which(candidate):
            return candidate
        if candidate and "\\" in candidate:
            try:
                with open(candidate, "rb"):
                    return candidate
            except OSError:
                continue
    return None
