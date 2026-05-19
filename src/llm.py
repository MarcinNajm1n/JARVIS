from __future__ import annotations

from dataclasses import dataclass
from collections.abc import Iterator
from typing import Any

from openai import OpenAI, OpenAIError

from src.config import Settings, load_settings, require_openai_api_key
from src.logger import get_logger


Message = dict[str, str]


@dataclass
class LLMClient:
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

    def trim_history(self, history: list[Message]) -> list[Message]:
        limit = self.settings.max_history_messages
        return history[-limit:]

    def build_instructions(
        self,
        long_term_memory: list[str],
        rag_context: str | None = None,
        user_profile: str | None = None,
        response_mode_instruction: str | None = None,
        project_context: str | None = None,
    ) -> str:
        sections = [self.settings.system_prompt]

        if response_mode_instruction:
            sections.append(response_mode_instruction)

        if user_profile:
            sections.append(f"Profil uzytkownika:\n{user_profile}")

        if project_context:
            sections.append(f"Kontekst aktywnego projektu:\n{project_context}")

        if long_term_memory:
            memory_items = "\n".join(f"- {item}" for item in long_term_memory)
            sections.append(
                "Trwala pamiec uzytkownika:\n"
                f"{memory_items}\n\n"
                "Traktuj te informacje jako fakty o uzytkowniku, dopoki rozmowa ich nie zmieni."
            )

        if rag_context:
            sections.append(
                "Kontekst z lokalnych dokumentow uzytkownika:\n"
                f"{rag_context}\n\n"
                "Korzystaj z tego kontekstu, gdy jest zwiazany z pytaniem. "
                "Jesli kontekst nie wystarcza, powiedz to wprost. "
                "Gdy wykorzystujesz RAG, podaj zrodlo w formie: Zrodlo: nazwa_pliku."
            )

        return "\n\n".join(sections)

    def generate_response(
        self,
        history: list[Message],
        long_term_memory: list[str],
        rag_context: str | None = None,
        user_profile: str | None = None,
        response_mode_instruction: str | None = None,
        project_context: str | None = None,
    ) -> str:
        try:
            instructions = self.build_instructions(
                long_term_memory=long_term_memory,
                rag_context=rag_context,
                user_profile=user_profile,
                response_mode_instruction=response_mode_instruction,
                project_context=project_context,
            )
            input_messages = self.trim_history(history)

            self._logger.debug("Calling OpenAI model: %s", self.settings.llm_model)
            response = self.client.responses.create(
                model=self.settings.llm_model,
                instructions=instructions,
                input=input_messages,
            )

            output_text = getattr(response, "output_text", None)
            if output_text:
                return str(output_text).strip()

            return self._extract_text_from_response(response)

        except OpenAIError as error:
            self._logger.exception("OpenAI LLM request failed")
            return f"Wystapil blad OpenAI API: {error}"
        except ValueError as error:
            self._logger.warning("LLM configuration error: %s", error)
            return f"Brakuje konfiguracji LLM: {error}"
        except Exception as error:
            self._logger.exception("Unexpected LLM error")
            return f"Wystapil nieoczekiwany blad programu: {error}"

    def stream_response(
        self,
        history: list[Message],
        long_term_memory: list[str],
        rag_context: str | None = None,
        user_profile: str | None = None,
        response_mode_instruction: str | None = None,
        project_context: str | None = None,
    ) -> Iterator[str]:
        try:
            instructions = self.build_instructions(
                long_term_memory=long_term_memory,
                rag_context=rag_context,
                user_profile=user_profile,
                response_mode_instruction=response_mode_instruction,
                project_context=project_context,
            )
            input_messages = self.trim_history(history)

            self._logger.debug("Streaming OpenAI model: %s", self.settings.llm_model)
            with self.client.responses.stream(
                model=self.settings.llm_model,
                instructions=instructions,
                input=input_messages,
            ) as stream:
                for event in stream:
                    event_type = getattr(event, "type", "")
                    if event_type == "response.output_text.delta":
                        delta = getattr(event, "delta", "")
                        if delta:
                            yield str(delta)
                stream.get_final_response()

        except OpenAIError as error:
            self._logger.exception("OpenAI streaming LLM request failed")
            yield f"Wystapil blad OpenAI API: {error}"
        except ValueError as error:
            self._logger.warning("LLM streaming configuration error: %s", error)
            yield f"Brakuje konfiguracji LLM: {error}"
        except Exception as error:
            self._logger.exception("Unexpected streaming LLM error")
            yield f"Wystapil nieoczekiwany blad programu: {error}"

    @staticmethod
    def _extract_text_from_response(response: Any) -> str:
        output_parts: list[str] = []

        for output_item in getattr(response, "output", []) or []:
            for content_item in getattr(output_item, "content", []) or []:
                text = getattr(content_item, "text", None)
                if text:
                    output_parts.append(str(text))

        if output_parts:
            return "\n".join(output_parts).strip()

        return "Nie udalo sie odczytac odpowiedzi modelu."
