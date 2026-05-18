from __future__ import annotations

from dataclasses import dataclass
from typing import Any

from src.config import Settings, load_settings
from src.json_store import read_json, write_json


DEFAULT_PROFILE = {
    "name": "Kornel",
    "field": "mechatronics",
    "goals": ["private AI assistant", "Python", "engineering workflow"],
    "response_style": "short, practical, technical",
}


@dataclass
class UserProfileStore:
    settings: Settings | None = None

    def __post_init__(self) -> None:
        self.settings = self.settings or load_settings()
        self._profile = DEFAULT_PROFILE | read_json(
            self.settings.user_profile_path,
            DEFAULT_PROFILE.copy(),
        )

    def get(self) -> dict[str, Any]:
        return self._profile

    def set_value(self, key: str, value: str) -> None:
        self._profile[key] = value
        self.save()

    def format_for_prompt(self) -> str:
        lines = []
        for key, value in self._profile.items():
            if isinstance(value, list):
                formatted_value = ", ".join(str(item) for item in value)
            else:
                formatted_value = str(value)
            lines.append(f"- {key}: {formatted_value}")
        return "\n".join(lines)

    def format_for_terminal(self) -> str:
        return self.format_for_prompt() or "Profil uzytkownika jest pusty."

    def save(self) -> None:
        write_json(self.settings.user_profile_path, self._profile)
