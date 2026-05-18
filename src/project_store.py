from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime
from typing import Any

from src.config import Settings, load_settings
from src.json_store import read_json, write_json


@dataclass
class ProjectStore:
    settings: Settings | None = None

    def __post_init__(self) -> None:
        self.settings = self.settings or load_settings()
        self._projects: dict[str, Any] = read_json(self.settings.project_store_path, {})

    def ensure_project(self, name: str) -> dict[str, Any]:
        normalized = self._normalize_name(name)
        if normalized not in self._projects:
            self._projects[normalized] = {
                "name": name.strip(),
                "notes": [],
                "created_at": datetime.now().isoformat(timespec="seconds"),
            }
            self.save()
        return self._projects[normalized]

    def add_note(self, project_name: str, note: str) -> None:
        project = self.ensure_project(project_name)
        project["notes"].append(
            {
                "content": note.strip(),
                "created_at": datetime.now().isoformat(timespec="seconds"),
            }
        )
        self.save()

    def summarize(self, project_name: str | None) -> str:
        if not project_name:
            return "Brak aktywnego projektu."

        project = self.ensure_project(project_name)
        notes = project.get("notes", [])[-5:]
        lines = [f"Aktywny projekt: {project['name']}"]
        if notes:
            lines.append("Ostatnie notatki:")
            lines.extend(f"- {note['content']}" for note in notes)
        return "\n".join(lines)

    def format_all(self) -> str:
        if not self._projects:
            return "Brak zapisanych projektow."

        lines = ["Projekty:"]
        for project in self._projects.values():
            lines.append(f"- {project['name']} ({len(project.get('notes', []))} notatek)")
        return "\n".join(lines)

    def save(self) -> None:
        write_json(self.settings.project_store_path, self._projects)

    @staticmethod
    def _normalize_name(name: str) -> str:
        return " ".join(name.strip().lower().split())
