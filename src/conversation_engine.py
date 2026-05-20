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
from src.cost_tracker import CostTracker
from src.episodic_memory import EpisodicMemoryStore
from src.function_tools import (
    JARVIS_FUNCTION_TOOLS,
    JarvisToolContext,
    execute_jarvis_tool,
)
from src.intent_router import RouteDecision, classify_intent
from src.llm import LLMClient, Message
from src.local_wake_detector import LocalWakeDetector
from src.logger import get_logger
from src.long_term_memory import (
    dodaj_wpis_pamieci,
    normalizuj_wpisy_pamieci,
    wczytaj_pamiec_stala,
    zapisz_pamiec_stala,
)
from src.memory_store import (
    wczytaj_historie,
    wczytaj_podsumowanie_historii,
    zapisz_historie,
)
from src.profile_store import UserProfileStore
from src.project_store import ProjectStore
from src.rag import RAGMemory
from src.response_modes import get_mode_instruction
from src.stt import SpeechToTextClient
from src.task_store import TaskStore
from src.transcript_corrector import TranscriptCorrector
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
        self._logger = get_logger(__name__)
        self.llm_client = LLMClient(self.settings)
        self.stt_client = SpeechToTextClient(self.settings)
        self.transcript_corrector = TranscriptCorrector(self.settings)
        self.wake_detector = LocalWakeDetector(self.stt_client)
        self.tts_client = TextToSpeechClient(self.settings)
        self.rag_memory = RAGMemory(self.settings)
        self.rag_memory.ensure_index()
        self.assistant_state = AssistantStateStore(self.settings)
        self.profile_store = UserProfileStore(self.settings)
        self.task_store = TaskStore(self.settings)
        self.project_store = ProjectStore(self.settings)
        self.episodic_memory = EpisodicMemoryStore(self.settings)
        self.cost_tracker = CostTracker(self.settings)
        self.last_route_decision: RouteDecision | None = None
        self.historia: list[Message] = wczytaj_historie(self.settings.history_path)
        self.history_enabled = self.settings.history_enabled
        self.podsumowanie_historii = wczytaj_podsumowanie_historii(
            self.settings.conversation_summary_path
        )
        self.pamiec_stala = wczytaj_pamiec_stala(self.settings.long_term_memory_path)
        self._active_speech_queue: ChunkedSpeechQueue | None = None

    def listen_once(self) -> tuple[str, float]:
        self.assistant_state.set_status(AssistantStatus.LISTENING)
        text = self.correct_transcript(self.stt_client.listen_and_transcribe() or "")
        return text, time.monotonic()

    def listen_for_command(self, max_seconds: int | None = None) -> tuple[str, float]:
        self.assistant_state.set_status(AssistantStatus.LISTENING_COMMAND)
        raw_text = self.stt_client.listen_and_transcribe(
            max_seconds=max_seconds or self.settings.command_timeout_seconds
        ) or ""
        text = self.correct_transcript(raw_text)
        return text, time.monotonic()

    def correct_transcript(self, text: str, allow_llm: bool = True) -> str:
        if not text.strip() or not self.settings.transcript_correction_enabled:
            return text

        result = self.transcript_corrector.correct(text)
        corrected_text = result.corrected_text
        if result.changed:
            self._logger.info(
                "Transcript corrected before command handling/LLM. corrections=%s confidence=%.2f",
                [correction.reason for correction in result.corrections],
                result.confidence,
            )
            self._logger.debug(
                "Transcript correction detail: original=%r corrected=%r",
                result.original_text,
                corrected_text,
            )

        if allow_llm and self.settings.transcript_correction_with_llm:
            llm_corrected = self.llm_client.correct_transcript(corrected_text)
            if llm_corrected != corrected_text:
                self._logger.info("Transcript corrected by LLM before command handling/LLM.")
                self._logger.debug(
                    "LLM transcript correction detail: original=%r corrected=%r",
                    corrected_text,
                    llm_corrected,
                )
                corrected_text = llm_corrected

        return corrected_text

    def acknowledge_wake_detected(self) -> None:
        self.assistant_state.set_status(AssistantStatus.WAKE_DETECTED)
        if czy_mowa_wlaczona():
            self.tts_client.speak("Słucham.", blocking=True)

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
        self._remember_turn("user", user_text)
        self.historia.append({"role": "user", "content": user_text})
        self.assistant_state.set_status(AssistantStatus.THINKING)
        self._logger.info("Sending command to LLM. Source: generate_response; length: %s", len(user_text))
        self._logger.info("OpenAI payload preview: %s", user_text[:240])
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
            conversation_summary=self.podsumowanie_historii,
            tools=self._get_function_tools(),
            tool_executor=self._execute_function_tool,
        )
        self.historia.append({"role": "assistant", "content": response})
        self._remember_turn("assistant", response)
        self._save_history()

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
        self._remember_turn("user", user_text)
        self.historia.append({"role": "user", "content": user_text})
        self.assistant_state.set_status(AssistantStatus.THINKING)
        self._logger.info("Sending command to LLM. Source: stream_response; length: %s", len(user_text))
        self._logger.info("OpenAI payload preview: %s", user_text[:240])
        yield ConversationEvent(AssistantStatus.THINKING.value.upper(), "")

        if self.settings.function_calling_enabled:
            final_response = self.llm_client.generate_response(
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
                conversation_summary=self.podsumowanie_historii,
                tools=self._get_function_tools(),
                tool_executor=self._execute_function_tool,
            )
            yield ConversationEvent(AssistantStatus.THINKING.value.upper(), final_response)
            if (
                czy_mowa_wlaczona()
                and final_response
                and not final_response.startswith("Wystapil blad")
            ):
                self.assistant_state.set_status(AssistantStatus.SPEAKING)
                yield ConversationEvent(AssistantStatus.SPEAKING.value.upper(), "")
                self.tts_client.speak(final_response, blocking=False)

            self.historia.append({"role": "assistant", "content": final_response})
            self._remember_turn("assistant", final_response)
            self._save_history()
            yield ConversationEvent(AssistantStatus.IDLE.value.upper(), final_response)
            return

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
            conversation_summary=self.podsumowanie_historii,
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
            self.tts_client.speak(final_response, blocking=False)

        self.historia.append({"role": "assistant", "content": final_response})
        self._remember_turn("assistant", final_response)
        self._save_history()
        yield ConversationEvent(AssistantStatus.IDLE.value.upper(), final_response)

    def _handle_command(self, user_text: str) -> tuple[bool, str]:
        self.last_route_decision = classify_intent(user_text)
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

    def _remember_turn(self, role: str, text: str) -> None:
        preview = text.strip()
        if len(preview) > 260:
            preview = f"{preview[:257]}..."
        self.episodic_memory.remember_event(role, preview)

    def _get_function_tools(self) -> list[dict] | None:
        if not self.settings.function_calling_enabled:
            return None
        return JARVIS_FUNCTION_TOOLS

    def _execute_function_tool(self, name: str, arguments: dict) -> str:
        context = JarvisToolContext(
            assistant_state=self.assistant_state,
            profile_store=self.profile_store,
            task_store=self.task_store,
            project_store=self.project_store,
            long_term_memory=self.pamiec_stala,
            long_term_memory_path=self.settings.long_term_memory_path,
            tool_call_log_path=self.settings.tool_call_log_path,
        )
        return execute_jarvis_tool(name, arguments, context)

    def get_memory_candidate(self, user_text: str) -> str | None:
        if not self.settings.auto_memory_enabled:
            return None
        candidate = extract_memory_candidate(user_text)
        if not candidate:
            return None
        existing = {
            entry["content"].lower()
            for entry in normalizuj_wpisy_pamieci(self.pamiec_stala)
        }
        if candidate.lower() in existing:
            return None
        return candidate

    def save_memory_candidate(self, candidate: str, memory_type: str = "facts") -> bool:
        entry = dodaj_wpis_pamieci(self.pamiec_stala, candidate, memory_type)
        if entry is None:
            return False
        zapisz_pamiec_stala(self.pamiec_stala, self.settings.long_term_memory_path)
        return True

    def _save_history(self) -> None:
        if not self.history_enabled:
            self._logger.info("History persistence disabled; skipping conversation_history write.")
            return
        zapisz_historie(
            self.historia,
            self.settings.history_path,
            sciezka_podsumowania=self.settings.conversation_summary_path,
        )
        self.historia = wczytaj_historie(self.settings.history_path)
        self.podsumowanie_historii = wczytaj_podsumowanie_historii(
            self.settings.conversation_summary_path
        )

    def _maybe_auto_memory(self, user_text: str) -> None:
        if not self.settings.auto_memory_enabled:
            return
        candidate = self.get_memory_candidate(user_text)
        if not candidate:
            return
        if self.settings.low_latency_mode:
            return

        decision = input(
            f"{NAZWA_ASYSTENTA}: Wykrylem potencjalny fakt do pamieci: "
            f"'{candidate}'. Zapisac? (tak/nie): "
        ).strip().lower()
        if decision == "tak":
            self.save_memory_candidate(candidate)

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
