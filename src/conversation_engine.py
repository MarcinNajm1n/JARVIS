from __future__ import annotations

import re
import time
from collections.abc import Iterator
from dataclasses import dataclass

from config import NAZWA_ASYSTENTA
from src.assistant_state import AssistantStateStore, AssistantStatus
from src.auto_memory import extract_memory_candidate
from src.command_handler import obsluz_komende
from src.config import Settings, load_settings
from src.llm import LLMClient, Message
from src.logger import get_logger
from src.long_term_memory import wczytaj_pamiec_stala, zapisz_pamiec_stala
from src.memory_store import wczytaj_historie, zapisz_historie
from src.profile_store import UserProfileStore
from src.project_store import ProjectStore
from src.rag import RAGMemory
from src.response_modes import get_mode_instruction
from src.stt import SpeechToTextClient
from src.task_store import TaskStore
from src.tts import ChunkedSpeechQueue, TextToSpeechClient
from src.voice_state import czy_mowa_wlaczona


class CriticalLatencyError(RuntimeError):
    pass


@dataclass(frozen=True)
class ConversationEvent:
    state: str
    payload: str

    def as_dict(self) -> dict[str, str]:
        return {"state": self.state, "payload": self.payload}


class LatencyTracker:
    def __init__(self, settings: Settings, utterance_end_time: float | None = None) -> None:
        self.settings = settings
        self.utterance_end_time = utterance_end_time or time.monotonic()
        self.first_sound_time: float | None = None
        self._logger = get_logger(__name__)

    def mark_first_sound(self) -> float:
        if self.first_sound_time is None:
            self.first_sound_time = time.monotonic()
            delta = self.first_sound_time - self.utterance_end_time
            if delta > self.settings.latency_critical_seconds:
                self._logger.error(
                    "First Jarvis sound exceeded critical latency: %.2fs", delta
                )
            elif delta > self.settings.latency_budget_seconds:
                self._logger.warning(
                    "First Jarvis sound exceeded latency budget: %.2fs", delta
                )
            else:
                self._logger.info("First Jarvis sound latency: %.2fs", delta)
        return self.first_sound_time - self.utterance_end_time


class ConversationEngine:
    def __init__(self, settings: Settings | None = None) -> None:
        self.settings = settings or load_settings()
        self.llm_client = LLMClient(self.settings)
        self.stt_client = SpeechToTextClient(self.settings)
        self.tts_client = TextToSpeechClient(self.settings)
        self.rag_memory = RAGMemory(self.settings)
        self.rag_memory.ensure_index()
        self.assistant_state = AssistantStateStore(self.settings)
        self.profile_store = UserProfileStore(self.settings)
        self.task_store = TaskStore(self.settings)
        self.project_store = ProjectStore(self.settings)
        self.historia: list[Message] = wczytaj_historie(self.settings.history_path)
        self.pamiec_stala = wczytaj_pamiec_stala(self.settings.long_term_memory_path)
        self._active_speech_queue: ChunkedSpeechQueue | None = None

    def listen_once(self) -> tuple[str, float]:
        self.assistant_state.set_status(AssistantStatus.LISTENING)
        text = self.stt_client.listen_and_transcribe() or ""
        return text, time.monotonic()

    def stop_audio(self) -> None:
        if self._active_speech_queue is not None:
            self._active_speech_queue.stop()
            self._active_speech_queue = None
        self.tts_client.stop()

    def stop_recording(self) -> None:
        self.stt_client.stop_recording()

    def stop_all(self) -> None:
        self.stop_recording()
        self.stop_audio()

    def generate_response(self, user_text: str, speak: bool = True) -> str:
        user_text = user_text.strip()
        if not user_text:
            return ""

        command_handled, payload = self._handle_command(user_text)
        if command_handled:
            return payload

        self._maybe_auto_memory(user_text)
        self.historia.append({"role": "user", "content": user_text})
        self.assistant_state.set_status(AssistantStatus.THINKING)
        response = self.llm_client.generate_response(
            history=self.historia,
            long_term_memory=self.pamiec_stala,
            rag_context=self.rag_memory.retrieve_context(user_text),
            user_profile=self.profile_store.format_for_prompt(),
            response_mode_instruction=get_mode_instruction(
                self.assistant_state.get_response_mode()
            ),
            project_context=self.project_store.summarize(
                self.assistant_state.get_active_project()
            ),
        )
        self.historia.append({"role": "assistant", "content": response})
        zapisz_historie(self.historia, self.settings.history_path)

        if speak and czy_mowa_wlaczona() and not response.startswith("Wystapil blad"):
            self.assistant_state.set_status(AssistantStatus.SPEAKING)
            self.tts_client.speak(response)

        return response

    def stream_response(
        self,
        user_text: str,
        utterance_end_time: float | None = None,
    ) -> Iterator[ConversationEvent]:
        user_text = user_text.strip()
        if not user_text:
            return

        command_handled, payload = self._handle_command(user_text)
        if command_handled:
            yield ConversationEvent(AssistantStatus.IDLE.value.upper(), payload)
            return

        self._maybe_auto_memory(user_text)
        self.historia.append({"role": "user", "content": user_text})
        self.assistant_state.set_status(AssistantStatus.THINKING)
        yield ConversationEvent(AssistantStatus.THINKING.value.upper(), "")

        tracker = LatencyTracker(self.settings, utterance_end_time)
        speech_queue = None
        if (
            czy_mowa_wlaczona()
            and self.settings.low_latency_mode
            and self.settings.streaming_tts
        ):
            speech_queue = self.tts_client.start_audio_queue(latency_tracker=tracker)
            self._active_speech_queue = speech_queue

        full_response: list[str] = []
        tts_buffer = ""
        stream = self.llm_client.stream_response(
            history=self.historia,
            long_term_memory=self.pamiec_stala,
            rag_context=self.rag_memory.retrieve_context(user_text),
            user_profile=self.profile_store.format_for_prompt(),
            response_mode_instruction=get_mode_instruction(
                self.assistant_state.get_response_mode()
            ),
            project_context=self.project_store.summarize(
                self.assistant_state.get_active_project()
            ),
        )

        for chunk in stream:
            full_response.append(chunk)
            tts_buffer += chunk
            yield ConversationEvent(AssistantStatus.THINKING.value.upper(), chunk)
            if speech_queue is not None:
                tts_buffer = self._flush_ready_tts_chunks(tts_buffer, speech_queue)

        final_response = "".join(full_response).strip()
        if tts_buffer.strip() and speech_queue is not None:
            speech_queue.enqueue_text(tts_buffer)
        if speech_queue is not None:
            self.assistant_state.set_status(AssistantStatus.SPEAKING)
            yield ConversationEvent(AssistantStatus.SPEAKING.value.upper(), "")
            speech_queue.close()
            speech_queue.wait()
        elif (
            czy_mowa_wlaczona()
            and final_response
            and not final_response.startswith("Wystapil blad")
        ):
            self.assistant_state.set_status(AssistantStatus.SPEAKING)
            yield ConversationEvent(AssistantStatus.SPEAKING.value.upper(), "")
            self.tts_client.speak(final_response, blocking=True)

        self.historia.append({"role": "assistant", "content": final_response})
        zapisz_historie(self.historia, self.settings.history_path)
        yield ConversationEvent(AssistantStatus.IDLE.value.upper(), final_response)

    def _handle_command(self, user_text: str) -> tuple[bool, str]:
        command_handled, self.historia, self.pamiec_stala = obsluz_komende(
            user_text,
            self.historia,
            self.pamiec_stala,
            sciezka_historii=self.settings.history_path,
            sciezka_pamieci_stalej=self.settings.long_term_memory_path,
            rag_memory=self.rag_memory,
            assistant_state=self.assistant_state,
            profile_store=self.profile_store,
            task_store=self.task_store,
            project_store=self.project_store,
            tts_client=self.tts_client,
        )
        return command_handled, "Komenda wykonana." if command_handled else ""

    def _maybe_auto_memory(self, user_text: str) -> None:
        if not self.settings.auto_memory_enabled:
            return
        candidate = extract_memory_candidate(user_text)
        if not candidate or candidate in self.pamiec_stala:
            return
        if self.settings.low_latency_mode:
            return

        decision = input(
            f"{NAZWA_ASYSTENTA}: Wykrylem potencjalny fakt do pamieci: "
            f"'{candidate}'. Zapisac? (tak/nie): "
        ).strip().lower()
        if decision == "tak":
            self.pamiec_stala.append(candidate)
            zapisz_pamiec_stala(self.pamiec_stala, self.settings.long_term_memory_path)

    @staticmethod
    def _flush_ready_tts_chunks(buffer: str, speech_queue: ChunkedSpeechQueue) -> str:
        while True:
            match = re.search(r"(.{40,220}?[.!?\n])\s+", buffer, flags=re.DOTALL)
            if match is None and len(buffer) < 180:
                return buffer
            if match is None:
                split_at = min(len(buffer), 180)
            else:
                split_at = match.end()
            speech_queue.enqueue_text(buffer[:split_at])
            buffer = buffer[split_at:]
