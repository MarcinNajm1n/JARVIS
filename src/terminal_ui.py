from __future__ import annotations

from dataclasses import dataclass

from src.assistant_state import AssistantStatus
from src.config import Settings, load_settings


@dataclass
class TerminalUI:
    settings: Settings | None = None

    def __post_init__(self) -> None:
        self.settings = self.settings or load_settings()
        self._console = None
        if self.settings.terminal_ui:
            try:
                from rich.console import Console

                self._console = Console()
            except Exception:
                self._console = None

    def status(self, status: AssistantStatus) -> None:
        label = f"[JARVIS: {status.value.upper()}]"
        if self._console:
            color = {
                AssistantStatus.SLEEPING: "dim cyan",
                AssistantStatus.WAKE_DETECTED: "green",
                AssistantStatus.LISTENING: "cyan",
                AssistantStatus.LISTENING_COMMAND: "bright_cyan",
                AssistantStatus.AWAKE_CONFIRM: "bright_magenta",
                AssistantStatus.ACTIVE_CONVERSATION: "green",
                AssistantStatus.WAITING_FOLLOWUP: "bright_cyan",
                AssistantStatus.GOING_SLEEP: "magenta",
                AssistantStatus.THINKING: "yellow",
                AssistantStatus.SPEAKING: "green",
                AssistantStatus.IDLE: "dim",
            }.get(status, "white")
            self._console.print(label, style=color)
            return

        print(label)

    def say(self, message: str) -> None:
        if self._console:
            self._console.print(message)
        else:
            print(message)
