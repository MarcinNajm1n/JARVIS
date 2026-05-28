from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path

import httpx

from src.config import Settings, load_settings
from src.logger import get_logger


ELEVENLABS_BASE_URL = "https://api.elevenlabs.io/v1"


@dataclass
class ElevenLabsVoiceClient:
    settings: Settings | None = None
    client: httpx.Client | None = None

    def __post_init__(self) -> None:
        self.settings = self.settings or load_settings()
        self._logger = get_logger(__name__)

    @property
    def available(self) -> bool:
        return bool(self.settings.elevenlabs_api_key)

    def generate_speech(self, text: str, output_path: Path) -> Path | None:
        if not text.strip() or not self.settings.elevenlabs_tts_enabled:
            return None
        if not self.available:
            self._logger.warning("Brakuje ELEVENLABS_API_KEY dla ElevenLabs TTS.")
            return None

        output_path.parent.mkdir(parents=True, exist_ok=True)
        url = (
            f"{ELEVENLABS_BASE_URL}/text-to-speech/{self.settings.elevenlabs_voice_id}"
            f"?output_format={self.settings.elevenlabs_output_format}"
        )
        payload = {
            "text": text,
            "model_id": self.settings.elevenlabs_tts_model,
            "language_code": self.settings.stt_language or "pl",
        }
        headers = {
            "xi-api-key": self.settings.elevenlabs_api_key or "",
            "Content-Type": "application/json",
            "Accept": "audio/mpeg",
        }
        try:
            response = self._post(url, headers=headers, json=payload)
            response.raise_for_status()
            output_path.write_bytes(response.content)
            return output_path
        except Exception as error:
            self._logger.warning("ElevenLabs TTS request failed: %s", error)
            return None

    def transcribe_audio(self, audio_path: Path) -> str | None:
        if not self.settings.elevenlabs_stt_enabled:
            return None
        if not self.available:
            self._logger.warning("Brakuje ELEVENLABS_API_KEY dla ElevenLabs STT.")
            return None
        if not audio_path.exists():
            self._logger.warning("Audio file does not exist: %s", audio_path)
            return None

        headers = {"xi-api-key": self.settings.elevenlabs_api_key or ""}
        data = {
            "model_id": self.settings.elevenlabs_stt_model,
            "language_code": self.settings.stt_language or "pl",
            "tag_audio_events": "false",
        }
        try:
            with audio_path.open("rb") as audio_file:
                files = {"file": (audio_path.name, audio_file, "audio/wav")}
                response = self._post(
                    f"{ELEVENLABS_BASE_URL}/speech-to-text",
                    headers=headers,
                    data=data,
                    files=files,
                )
            response.raise_for_status()
            payload = response.json()
            text = str(payload.get("text") or "").strip()
            return text or None
        except Exception as error:
            self._logger.warning("ElevenLabs STT request failed: %s", error)
            return None

    def _post(self, url: str, **kwargs) -> httpx.Response:
        if self.client is not None:
            return self.client.post(url, **kwargs)
        with httpx.Client(timeout=self.settings.elevenlabs_timeout_seconds) as client:
            return client.post(url, **kwargs)
