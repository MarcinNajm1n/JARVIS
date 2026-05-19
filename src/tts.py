from __future__ import annotations

import queue
import threading
from dataclasses import dataclass
from collections.abc import Iterable, Iterator
from pathlib import Path

from openai import OpenAI, OpenAIError

from src.config import Settings, load_settings, require_openai_api_key
from src.logger import get_logger


class ChunkedSpeechQueue:
    def __init__(self, client: "TextToSpeechClient", latency_tracker=None) -> None:
        self._client = client
        self._latency_tracker = latency_tracker
        self._text_queue: queue.Queue[str | None] = queue.Queue()
        self._audio_queue: queue.Queue[Path | None] = queue.Queue()
        self._stop_requested = threading.Event()
        self._generator = threading.Thread(target=self._generate_audio, daemon=True)
        self._player = threading.Thread(target=self._play_audio, daemon=True)
        self._generator.start()
        self._player.start()

    def enqueue_text(self, text: str) -> None:
        text = text.strip()
        if text:
            self._text_queue.put(text)

    def close(self) -> None:
        self._text_queue.put(None)

    def wait(self) -> None:
        self._generator.join()
        self._player.join()

    def stop(self) -> None:
        self._stop_requested.set()
        self._client.stop()
        self._text_queue.put(None)
        self._audio_queue.put(None)

    def _generate_audio(self) -> None:
        index = 0
        while not self._stop_requested.is_set():
            text = self._text_queue.get()
            if text is None:
                break
            audio_path = self._client.generate_speech(
                text,
                self._client.segment_path(index),
            )
            index += 1
            if audio_path is not None:
                self._audio_queue.put(audio_path)
        self._audio_queue.put(None)

    def _play_audio(self) -> None:
        try:
            first_segment = True
            while not self._stop_requested.is_set():
                audio_path = self._audio_queue.get()
                if audio_path is None:
                    break
                if first_segment and self._latency_tracker is not None:
                    self._latency_tracker.mark_first_sound()
                    first_segment = False
                self._client.play_audio(audio_path)
        except Exception as error:
            self._client._logger.warning("Chunked audio playback stopped: %s", error)


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

    def segment_path(self, index: int) -> Path:
        segment_dir = self.settings.tts_output_path.parent / "tts_segments"
        segment_dir.mkdir(parents=True, exist_ok=True)
        return segment_dir / f"segment_{index:04d}.mp3"

    def stream(self, text_iter: Iterable[str]) -> Iterator[Path]:
        for index, text in enumerate(text_iter):
            audio_path = self.generate_speech(text, self.segment_path(index))
            if audio_path is not None:
                yield audio_path

    def start_audio_queue(self, latency_tracker=None) -> ChunkedSpeechQueue:
        return ChunkedSpeechQueue(self, latency_tracker=latency_tracker)

    def speak_stream(self, text_iter: Iterable[str], latency_tracker=None) -> bool:
        speech_queue = self.start_audio_queue(latency_tracker=latency_tracker)
        for text in text_iter:
            speech_queue.enqueue_text(text)
        speech_queue.close()
        return True

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
