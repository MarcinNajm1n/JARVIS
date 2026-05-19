from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime
from typing import Any

from src.config import Settings, load_settings
from src.json_store import read_json, write_json


@dataclass
class FeedbackStore:
    settings: Settings | None = None

    def __post_init__(self) -> None:
        self.settings = self.settings or load_settings()
        self._items: list[dict[str, Any]] = read_json(self.settings.feedback_path, [])
        if not isinstance(self._items, list):
            self._items = []

    def add(self, rating: str, note: str = "") -> dict[str, Any]:
        item = {
            "id": len(self._items) + 1,
            "rating": rating,
            "note": note.strip(),
            "created_at": datetime.now().isoformat(timespec="seconds"),
        }
        self._items.append(item)
        self.save()
        return item

    def save(self) -> None:
        write_json(self.settings.feedback_path, self._items)
