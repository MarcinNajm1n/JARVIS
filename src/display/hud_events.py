from __future__ import annotations

import time
from contextlib import contextmanager
from typing import Iterator


class HudOperationTimeline:
    def __init__(self) -> None:
        self.operations: list[dict] = []

    def add(self, name: str, status: str = "done", duration_ms: int = 0, detail: str | None = None) -> None:
        self.operations.append(
            {
                "name": name,
                "status": status,
                "duration_ms": duration_ms,
                "detail": detail,
            }
        )

    @contextmanager
    def timed(self, name: str) -> Iterator[None]:
        started = time.perf_counter()
        try:
            yield
        except Exception as error:
            self.add(name, "failed", int((time.perf_counter() - started) * 1000), str(error))
            raise
        else:
            self.add(name, "done", int((time.perf_counter() - started) * 1000))
