from __future__ import annotations

from dataclasses import dataclass
from enum import StrEnum

from src.config import Settings, load_settings
from src.json_store import read_json, write_json


class AssistantStatus(StrEnum):
    SLEEPING = "sleeping"
    WAKE_DETECTED = "wake_detected"
    LISTENING = "listening"
    LISTENING_COMMAND = "listening_command"
    AWAKE_CONFIRM = "awake_confirm"
    ACTIVE_CONVERSATION = "active_conversation"
    WAITING_FOLLOWUP = "waiting_followup"
    GOING_SLEEP = "going_sleep"
    THINKING = "thinking"
    SPEAKING = "speaking"
    IDLE = "idle"


DEFAULT_STATE = {
    "response_mode": "jarvis",
    "active_project": None,
    "last_status": AssistantStatus.IDLE.value,
}


@dataclass
class AssistantStateStore:
    settings: Settings | None = None

    def __post_init__(self) -> None:
        self.settings = self.settings or load_settings()
        self._state = DEFAULT_STATE | read_json(
            self.settings.assistant_state_path,
            DEFAULT_STATE.copy(),
        )

    def get_response_mode(self) -> str:
        return str(self._state.get("response_mode", "jarvis"))

    def set_response_mode(self, mode: str) -> None:
        self._state["response_mode"] = mode
        self.save()

    def get_active_project(self) -> str | None:
        value = self._state.get("active_project")
        return str(value) if value else None

    def set_active_project(self, project_name: str | None) -> None:
        self._state["active_project"] = project_name
        self.save()

    def set_status(self, status: AssistantStatus) -> None:
        self._state["last_status"] = status.value
        self.save()

    def get_status(self) -> str:
        return str(self._state.get("last_status", AssistantStatus.IDLE.value))

    def save(self) -> None:
        write_json(self.settings.assistant_state_path, self._state)
