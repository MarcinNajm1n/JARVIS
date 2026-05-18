from __future__ import annotations

import math
import re
import unicodedata
import wave
from dataclasses import dataclass
from pathlib import Path

from openai import OpenAI, OpenAIError

from src.config import Settings, load_settings, require_openai_api_key
from src.logger import get_logger


COMMON_SILENCE_HALLUCINATIONS = {
    "thank you for watching",
    "thanks for watching",
    "please subscribe",
    "lets go",
    "let s go",
    "\u3054\u89a7\u3044\u305f\u3060\u304d\u3042\u308a\u304c\u3068\u3046\u3054\u3056\u3044\u307e\u3059",
    "\u30c1\u30e3\u30f3\u30cd\u30eb\u767b\u9332\u3092\u304a\u9858\u3044\u3044\u305f\u3057\u307e\u3059",
}


@dataclass(frozen=True)
class AudioCaptureResult:
    path: Path
    speech_detected: bool
    duration_seconds: float
    rms: float


@dataclass
class SpeechToTextClient:
    settings: Settings | None = None

    def __post_init__(self) -> None:
        self.settings = self.settings or load_settings()
        self._client: OpenAI | None = None
        self._logger = get_logger(__name__)

    @property
    def client(self) -> OpenAI:
        if self._client is None:
            api_key = require_openai_api_key(self.settings)
            self._client = OpenAI(api_key=api_key)
        return self._client

    def record_microphone(
        self,
        output_path: Path | None = None,
        max_seconds: int | None = None,
    ) -> Path | None:
        result = self.record_until_silence(output_path=output_path, max_seconds=max_seconds)
        if result is None or not result.speech_detected:
            return None
        return result.path

    def record_until_silence(
        self,
        output_path: Path | None = None,
        max_seconds: int | None = None,
    ) -> AudioCaptureResult | None:
        output_path = output_path or self.settings.microphone_temp_path
        output_path.parent.mkdir(parents=True, exist_ok=True)
        max_seconds = max_seconds or self.settings.record_seconds

        try:
            import numpy as np
            import sounddevice as sd

            sample_rate = self.settings.sample_rate
            chunk_size = max(1, int(sample_rate * self.settings.audio_chunk_seconds))
            max_chunks = max(1, math.ceil(max_seconds / self.settings.audio_chunk_seconds))
            silence_chunks_limit = max(
                1,
                math.ceil(
                    self.settings.speech_end_silence_seconds
                    / self.settings.audio_chunk_seconds
                ),
            )
            pre_speech_chunks_limit = max(
                1,
                math.ceil(0.35 / self.settings.audio_chunk_seconds),
            )

            self._logger.info(
                "Recording microphone until silence or %s seconds", max_seconds
            )

            recorded_chunks = []
            pre_speech_chunks = []
            speech_started = False
            silent_chunks_after_speech = 0
            max_rms = 0.0

            with sd.InputStream(
                samplerate=sample_rate,
                channels=1,
                dtype="int16",
                blocksize=chunk_size,
            ) as stream:
                for _ in range(max_chunks):
                    chunk, _overflowed = stream.read(chunk_size)
                    chunk = chunk.copy()
                    rms = self._calculate_rms(chunk)
                    max_rms = max(max_rms, rms)
                    has_speech = rms >= self.settings.speech_rms_threshold

                    if has_speech and not speech_started:
                        speech_started = True
                        recorded_chunks.extend(pre_speech_chunks)

                    if speech_started:
                        recorded_chunks.append(chunk)
                        silent_chunks_after_speech = (
                            0 if has_speech else silent_chunks_after_speech + 1
                        )
                        if silent_chunks_after_speech >= silence_chunks_limit:
                            break
                    else:
                        pre_speech_chunks.append(chunk)
                        pre_speech_chunks = pre_speech_chunks[-pre_speech_chunks_limit:]

            if not speech_started or not recorded_chunks:
                return AudioCaptureResult(
                    path=output_path,
                    speech_detected=False,
                    duration_seconds=0.0,
                    rms=max_rms,
                )

            audio_data = np.concatenate(recorded_chunks, axis=0)
            duration_seconds = len(audio_data) / sample_rate
            overall_rms = self._calculate_rms(audio_data)

            if duration_seconds < self.settings.min_speech_seconds:
                return AudioCaptureResult(
                    path=output_path,
                    speech_detected=False,
                    duration_seconds=duration_seconds,
                    rms=overall_rms,
                )

            with wave.open(str(output_path), "wb") as audio_file:
                audio_file.setnchannels(1)
                audio_file.setsampwidth(2)
                audio_file.setframerate(sample_rate)
                audio_file.writeframes(audio_data.tobytes())

            return AudioCaptureResult(
                path=output_path,
                speech_detected=True,
                duration_seconds=duration_seconds,
                rms=overall_rms,
            )

        except Exception as error:
            self._logger.warning("Microphone recording failed: %s", error)
            return None

    def transcribe_audio(self, audio_path: Path) -> str | None:
        if not audio_path.exists():
            self._logger.warning("Audio file does not exist: %s", audio_path)
            return None

        try:
            with audio_path.open("rb") as audio_file:
                transcript = self.client.audio.transcriptions.create(
                    model=self.settings.stt_model,
                    file=audio_file,
                    response_format="text",
                    language=self.settings.stt_language,
                    prompt=self.settings.stt_prompt,
                )

            if isinstance(transcript, str):
                text = transcript.strip()
            else:
                text = str(getattr(transcript, "text", "")).strip()

            if not text or self._looks_like_silence_hallucination(text):
                return None

            return text

        except OpenAIError as error:
            self._logger.warning("OpenAI STT request failed: %s", error)
            return None
        except ValueError as error:
            self._logger.warning("STT configuration error: %s", error)
            return None
        except Exception as error:
            self._logger.warning("Unexpected STT error: %s", error)
            return None

    def listen_and_transcribe(self, max_seconds: int | None = None) -> str | None:
        capture = self.record_until_silence(max_seconds=max_seconds)
        if capture is None:
            return None

        if not capture.speech_detected:
            self._logger.info("No speech detected; max RMS was %.1f", capture.rms)
            return None

        return self.transcribe_audio(capture.path)

    def contains_wake_phrase(self, text: str) -> bool:
        normalized_text = self._normalize_for_matching(text)
        normalized_wake_phrase = self._normalize_for_matching(self.settings.wake_phrase)

        if normalized_wake_phrase and normalized_wake_phrase in normalized_text:
            return True

        wake_aliases = {"jarvis", "dzarvis", "jervis"}
        has_name = any(alias in normalized_text for alias in wake_aliases)
        return has_name and "aktywacja" in normalized_text

    @staticmethod
    def _calculate_rms(audio_data) -> float:
        try:
            import numpy as np

            audio_float = audio_data.astype(np.float32)
            return float(np.sqrt(np.mean(np.square(audio_float))))
        except Exception:
            return 0.0

    @staticmethod
    def _normalize_for_matching(text: str) -> str:
        text = text.strip().lower()
        text = unicodedata.normalize("NFKD", text)
        text = "".join(character for character in text if not unicodedata.combining(character))
        text = re.sub(r"[^a-z0-9 ]+", " ", text)
        return " ".join(text.split())

    def _looks_like_silence_hallucination(self, text: str) -> bool:
        normalized = self._normalize_for_matching(text)
        if len(normalized) <= 1:
            return True

        if any("\u3040" <= character <= "\u30ff" or "\u4e00" <= character <= "\u9fff" for character in text):
            self._logger.info("Ignoring non-Polish STT hallucination: %s", text)
            return True

        return normalized in COMMON_SILENCE_HALLUCINATIONS
