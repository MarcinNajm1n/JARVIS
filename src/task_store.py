from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime
from typing import Any

from src.config import Settings, load_settings
from src.json_store import read_json, write_json


@dataclass
class TaskStore:
    settings: Settings | None = None

    def __post_init__(self) -> None:
        self.settings = self.settings or load_settings()
        self._tasks: list[dict[str, Any]] = read_json(self.settings.task_store_path, [])

    def add(self, title: str) -> dict[str, Any]:
        next_id = max((int(task.get("id", 0)) for task in self._tasks), default=0) + 1
        task = {
            "id": next_id,
            "title": title.strip(),
            "done": False,
            "created_at": datetime.now().isoformat(timespec="seconds"),
        }
        self._tasks.append(task)
        self.save()
        return task

    def list(self, include_done: bool = True) -> list[dict[str, Any]]:
        if include_done:
            return list(self._tasks)
        return [task for task in self._tasks if not task.get("done", False)]

    def mark_done(self, task_id: int) -> bool:
        for task in self._tasks:
            if int(task.get("id", -1)) == task_id:
                task["done"] = True
                task["done_at"] = datetime.now().isoformat(timespec="seconds")
                self.save()
                return True
        return False

    def remove(self, task_id: int) -> bool:
        old_count = len(self._tasks)
        self._tasks = [task for task in self._tasks if int(task.get("id", -1)) != task_id]
        changed = len(self._tasks) != old_count
        if changed:
            self.save()
        return changed

    def format(self) -> str:
        if not self._tasks:
            return "Lista zadan jest pusta."

        lines = ["Zadania:"]
        for task in self._tasks:
            marker = "x" if task.get("done") else " "
            lines.append(f"{task['id']}. [{marker}] {task['title']}")
        return "\n".join(lines)

    def save(self) -> None:
        write_json(self.settings.task_store_path, self._tasks)
