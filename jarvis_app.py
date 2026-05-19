from __future__ import annotations

import threading

from src.app_launcher import app_url, find_free_port, open_app_window, run_server, wait_until_ready


def main() -> None:
    port = find_free_port()
    url = app_url(port)
    threading.Thread(
        target=lambda: open_app_window(url) if wait_until_ready(port) else None,
        daemon=True,
    ).start()
    run_server(port)


if __name__ == "__main__":
    main()
