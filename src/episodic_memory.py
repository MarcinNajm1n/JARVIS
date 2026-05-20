from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime
from typing import Any

from src.config import Settings, load_settings
from src.json_store import read_json, write_json


@dataclass
class EpisodicMemoryStore:
    settings: Settings | None = None

    def __post_init__(self) -> None:
        self.settings = self.settings or load_settings()
        self._data = read_json(self.settings.episodic_memory_path, {"events": []})

    def remember_event(self, event_type: str, content: str) -> None:
        content = content.strip()
        if not content:
            return
        events = self._data.setdefault("events", [])
        events.append(
            {
                "type": event_type,
                "content": content,
                "created_at": datetime.now().isoformat(timespec="seconds"),
            }
        )
        self._data["events"] = events[-80:]
        self.save()

    def recent_context(self, limit: int = 5) -> str:
        events: list[dict[str, Any]] = self._data.get("events", [])
        if not events:
            return "Brak epizodycznego kontekstu rozmowy."
        lines = ["Ostatni kontekst rozmowy:"]
        for event in events[-limit:]:
            lines.append(f"- [{event.get('type', 'event')}] {event.get('content', '')}")
        return "\n".join(lines)

    def snapshot(self) -> dict[str, Any]:
        events: list[dict[str, Any]] = self._data.get("events", [])
        return {
            "events_count": len(events),
            "recent_context": self.recent_context(),
        }

    def save(self) -> None:
        write_json(self.settings.episodic_memory_path, self._data)
