from __future__ import annotations

import json
from dataclasses import dataclass
from collections.abc import Iterator
from typing import Any, Callable

from openai import OpenAI, OpenAIError

from src.command_catalog import format_command_catalog_for_prompt
from src.config import Settings, load_settings, require_openai_api_key
from src.cost_tracker import CostTracker, extract_response_usage
from src.logger import get_logger
from src.long_term_memory import formatuj_pamiec_do_promptu


Message = dict[str, Any]
ToolExecutor = Callable[[str, dict[str, Any]], str]


@dataclass
class LLMClient:
    settings: Settings | None = None

    def __post_init__(self) -> None:
        self.settings = self.settings or load_settings()
        self._client: OpenAI | None = None
        self._logger = get_logger(__name__)
        self.cost_tracker = CostTracker(self.settings)

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
        conversation_summary: str | None = None,
    ) -> str:
        sections = [self.settings.system_prompt]

        if response_mode_instruction:
            sections.append(response_mode_instruction)

        if user_profile:
            sections.append(f"Profil uzytkownika:\n{user_profile}")

        if project_context:
            sections.append(f"Kontekst aktywnego projektu:\n{project_context}")

        if conversation_summary:
            sections.append(f"Skrot starszej rozmowy:\n{conversation_summary}")

        sections.append(format_command_catalog_for_prompt())

        if long_term_memory:
            memory_items = formatuj_pamiec_do_promptu(long_term_memory)
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
        conversation_summary: str | None = None,
        tools: list[dict[str, Any]] | None = None,
        tool_executor: ToolExecutor | None = None,
    ) -> str:
        try:
            instructions = self.build_instructions(
                long_term_memory=long_term_memory,
                rag_context=rag_context,
                user_profile=user_profile,
                response_mode_instruction=response_mode_instruction,
                project_context=project_context,
                conversation_summary=conversation_summary,
            )
            input_messages = self.trim_history(history)

            self._logger.debug("Calling OpenAI model: %s", self.settings.llm_model)
            response = self._create_response(
                instructions=instructions,
                input_messages=input_messages,
                tools=tools,
                source="generate_response",
            )

            if tools and tool_executor:
                return self._resolve_tool_calls(
                    response=response,
                    instructions=instructions,
                    input_messages=input_messages,
                    tools=tools,
                    tool_executor=tool_executor,
                )

            return self._extract_response_text(response)

        except OpenAIError as error:
            self._logger.exception("OpenAI LLM request failed")
            return "Wystapil blad OpenAI API. Szczegoly zapisano w lokalnych logach."
        except ValueError as error:
            self._logger.warning("LLM configuration error: %s", error)
            return f"Brakuje konfiguracji LLM: {error}"
        except Exception as error:
            self._logger.exception("Unexpected LLM error")
            return "Wystapil nieoczekiwany blad programu. Szczegoly zapisano w lokalnych logach."

    def correct_transcript(self, text: str) -> str:
        text = text.strip()
        if not text:
            return text

        instructions = (
            "Popraw tylko oczywiste bledy STT w polsko-angielskiej komendzie "
            "technicznej do asystenta JARVIS. Nie dopowiadaj nowych intencji, "
            "nie zmieniaj sensu i zwroc wylacznie poprawiony tekst."
        )
        try:
            response = self.client.responses.create(
                model=self.settings.llm_model,
                instructions=instructions,
                input=[{"role": "user", "content": text}],
            )
            self._record_usage(response, "correct_transcript")
            corrected = self._extract_response_text(response).strip().strip('"').strip("'")
            max_reasonable_length = max(len(text) * 2, len(text) + 80)
            if not corrected or len(corrected) > max_reasonable_length:
                self._logger.warning("LLM transcript correction rejected as unsafe.")
                return text
            return corrected
        except OpenAIError:
            self._logger.exception("OpenAI transcript correction failed")
            return text
        except ValueError as error:
            self._logger.warning("Transcript correction configuration error: %s", error)
            return text
        except Exception:
            self._logger.exception("Unexpected transcript correction error")
            return text

    def _create_response(
        self,
        instructions: str,
        input_messages: list[Message],
        tools: list[dict[str, Any]] | None = None,
        source: str = "responses_api",
    ) -> Any:
        request: dict[str, Any] = {
            "model": self.settings.llm_model,
            "instructions": instructions,
            "input": input_messages,
        }
        if tools:
            request["tools"] = tools
            request["tool_choice"] = "auto"

        response = self.client.responses.create(**request)
        self._record_usage(response, source)
        return response

    def _resolve_tool_calls(
        self,
        response: Any,
        instructions: str,
        input_messages: list[Message],
        tools: list[dict[str, Any]],
        tool_executor: ToolExecutor,
        max_rounds: int = 3,
    ) -> str:
        current_response = response
        current_input: list[Any] = list(input_messages)

        for _round in range(max_rounds):
            function_calls = self._extract_function_calls(current_response)
            if not function_calls:
                return self._extract_response_text(current_response)

            current_input.extend(getattr(current_response, "output", []) or [])
            for function_call in function_calls:
                result = tool_executor(function_call["name"], function_call["arguments"])
                current_input.append(
                    {
                        "type": "function_call_output",
                        "call_id": function_call["call_id"],
                        "output": result,
                    }
                )

            current_response = self._create_response(
                instructions=instructions,
                input_messages=current_input,
                tools=tools,
                source="tool_followup",
            )

        return "Nie udalo sie zakonczyc wywolan narzedzi w bezpiecznym limicie rund."

    def stream_response(
        self,
        history: list[Message],
        long_term_memory: list[str],
        rag_context: str | None = None,
        user_profile: str | None = None,
        response_mode_instruction: str | None = None,
        project_context: str | None = None,
        conversation_summary: str | None = None,
    ) -> Iterator[str]:
        try:
            instructions = self.build_instructions(
                long_term_memory=long_term_memory,
                rag_context=rag_context,
                user_profile=user_profile,
                response_mode_instruction=response_mode_instruction,
                project_context=project_context,
                conversation_summary=conversation_summary,
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
                final_response = stream.get_final_response()
                self._record_usage(final_response, "stream_response")

        except OpenAIError as error:
            self._logger.exception("OpenAI streaming LLM request failed")
            yield "Wystapil blad OpenAI API. Szczegoly zapisano w lokalnych logach."
        except ValueError as error:
            self._logger.warning("LLM streaming configuration error: %s", error)
            yield f"Brakuje konfiguracji LLM: {error}"
        except Exception as error:
            self._logger.exception("Unexpected streaming LLM error")
            yield "Wystapil nieoczekiwany blad programu. Szczegoly zapisano w lokalnych logach."

    @staticmethod
    def _extract_function_calls(response: Any) -> list[dict[str, Any]]:
        calls: list[dict[str, Any]] = []

        for output_item in getattr(response, "output", []) or []:
            if getattr(output_item, "type", None) != "function_call":
                continue

            raw_arguments = getattr(output_item, "arguments", "{}") or "{}"
            if isinstance(raw_arguments, dict):
                arguments = raw_arguments
            else:
                arguments = json.loads(str(raw_arguments))

            calls.append(
                {
                    "call_id": str(getattr(output_item, "call_id", "")),
                    "name": str(getattr(output_item, "name", "")),
                    "arguments": arguments,
                }
            )

        return calls

    def _record_usage(self, response: Any, source: str) -> None:
        input_tokens, output_tokens = extract_response_usage(response)
        if not input_tokens and not output_tokens:
            return
        self.cost_tracker.record_llm_usage(
            model=self.settings.llm_model,
            input_tokens=input_tokens,
            output_tokens=output_tokens,
            source=source,
        )

    @classmethod
    def _extract_response_text(cls, response: Any) -> str:
        output_text = getattr(response, "output_text", None)
        if output_text:
            return str(output_text).strip()

        return cls._extract_text_from_response(response)

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
