from __future__ import annotations

from dataclasses import dataclass

from src.stt import SpeechToTextClient
from src.voice_commands import is_activation_command


@dataclass
class WakeDetectionResult:
    activated: bool
    method: str
    confidence: float


class LocalWakeDetector:
    """Interface for a future local wake-word engine, currently backed by text intent."""

    def __init__(self, stt_client: SpeechToTextClient) -> None:
        self.stt_client = stt_client

    def detect_from_text(self, text: str) -> WakeDetectionResult:
        if is_activation_command(text):
            return WakeDetectionResult(True, "local_intent", 0.9)
        if self.stt_client.contains_wake_phrase(text):
            return WakeDetectionResult(True, "stt_phrase", 0.82)
        return WakeDetectionResult(False, "none", 0.0)

    def status(self) -> str:
        return "local-text-intent-ready; audio wake model: planned"
