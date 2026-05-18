from __future__ import annotations

import threading
from dataclasses import dataclass
from pathlib import Path

from openai import OpenAI, OpenAIError

from src.config import Settings, load_settings, require_openai_api_key
from src.logger import get_logger


@dataclass
class TextToSpeechClient:
    settings: Settings | None = None

    def __post_init__(self) -> None:
        self.settings = self.settings or load_settings()
        self._client: OpenAI | None = None
        self._logger = get_logger(__name__)
        self._playback_thread: threading.Thread | None = None
        self._stop_requested = threading.Event()

    @property
    def client(self) -> OpenAI:
        if self._client is None:
            api_key = require_openai_api_key(self.settings)
            self._client = OpenAI(api_key=api_key)
        return self._client

    def generate_speech(self, text: str, output_path: Path | None = None) -> Path | None:
        if not text.strip() or not self.settings.tts_enabled:
            return None

        output_path = output_path or self.settings.tts_output_path
        output_path.parent.mkdir(parents=True, exist_ok=True)

        try:
            with self.client.audio.speech.with_streaming_response.create(
                model=self.settings.tts_model,
                voice=self.settings.tts_voice,
                input=text,
                instructions="Mow po polsku, spokojnie, technicznie i rzeczowo.",
            ) as response:
                response.stream_to_file(output_path)

            return output_path

        except OpenAIError as error:
            self._logger.warning("OpenAI TTS request failed: %s", error)
            return None
        except ValueError as error:
            self._logger.warning("TTS configuration error: %s", error)
            return None
        except Exception as error:
            self._logger.warning("Unexpected TTS error: %s", error)
            return None

    def play_audio(self, audio_path: Path) -> bool:
        if not audio_path.exists():
            return False

        try:
            import pygame

            self._stop_requested.clear()
            pygame.mixer.init()
            pygame.mixer.music.load(str(audio_path))
            pygame.mixer.music.play()

            while pygame.mixer.music.get_busy():
                if self._stop_requested.is_set():
                    pygame.mixer.music.stop()
                    break
                pygame.time.Clock().tick(10)

            pygame.mixer.quit()
            return True

        except Exception as error:
            self._logger.warning("Audio playback failed: %s", error)
            return False

    def speak(self, text: str, blocking: bool | None = None) -> bool:
        audio_path = self.generate_speech(text)
        if audio_path is None:
            return False

        should_block = not self.settings.tts_async_playback if blocking is None else blocking
        if should_block:
            return self.play_audio(audio_path)

        self.stop()
        self._playback_thread = threading.Thread(
            target=self.play_audio,
            args=(audio_path,),
            daemon=True,
        )
        self._playback_thread.start()
        return True

    def stop(self) -> None:
        self._stop_requested.set()
        try:
            import pygame

            if pygame.mixer.get_init():
                pygame.mixer.music.stop()
        except Exception:
            return
