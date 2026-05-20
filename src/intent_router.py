from __future__ import annotations

from dataclasses import dataclass
from enum import StrEnum

from src.voice_commands import (
    is_activation_command,
    is_shutdown_command,
    is_tts_stop_command,
    normalize_voice_command,
)
from src.weather_service import is_weather_query


class IntentType(StrEnum):
    ACTIVATION = "activation"
    SLEEP = "sleep"
    SHUTDOWN = "shutdown"
    STOP_TTS = "stop_tts"
    REPEAT = "repeat"
    VOLUME_DOWN = "volume_down"
    VOLUME_UP = "volume_up"
    REMEMBER = "remember"
    FORGET = "forget"
    STATUS = "status"
    PROJECT_STATUS = "project_status"
    WEATHER_QUERY = "weather_query"
    RAG_QUERY = "rag_query"
    TOOL = "tool"
    LLM = "llm"


class RouteType(StrEnum):
    LOCAL = "local"
    MEMORY = "memory"
    RAG = "rag"
    TOOL = "tool"
    LLM = "llm"


@dataclass(frozen=True)
class RouteDecision:
    intent: IntentType
    route: RouteType
    confidence: float
    reason: str


def classify_intent(text: str) -> RouteDecision:
    normalized = normalize_voice_command(text)
    tokens = set(normalized.split())

    if is_shutdown_command(text):
        return RouteDecision(IntentType.SHUTDOWN, RouteType.LOCAL, 0.95, "shutdown intent")
    if is_tts_stop_command(text):
        return RouteDecision(IntentType.STOP_TTS, RouteType.LOCAL, 0.95, "stop tts intent")
    if is_activation_command(text):
        return RouteDecision(IntentType.ACTIVATION, RouteType.LOCAL, 0.9, "activation intent")

    if _contains_any(normalized, ("idz spac", "mozesz spac", "wracaj spac", "uspij sie")):
        return RouteDecision(IntentType.SLEEP, RouteType.LOCAL, 0.86, "sleep intent")
    if _contains_any(normalized, ("powtorz", "jeszcze raz", "co powiedziales")):
        return RouteDecision(IntentType.REPEAT, RouteType.LOCAL, 0.84, "repeat intent")
    if _contains_any(normalized, ("ciszej", "scisz", "mow ciszej")):
        return RouteDecision(IntentType.VOLUME_DOWN, RouteType.LOCAL, 0.82, "volume down intent")
    if _contains_any(normalized, ("glosniej", "podglos", "mow glosniej")):
        return RouteDecision(IntentType.VOLUME_UP, RouteType.LOCAL, 0.82, "volume up intent")
    if _contains_any(normalized, ("pokaz status", "jaki status", "status systemu", "co z projektem")):
        intent = IntentType.PROJECT_STATUS if "projekt" in tokens else IntentType.STATUS
        return RouteDecision(intent, RouteType.LOCAL, 0.86, "status intent")
    if is_weather_query(text):
        return RouteDecision(IntentType.WEATHER_QUERY, RouteType.TOOL, 0.88, "weather query intent")
    if _contains_any(normalized, ("zapamietaj", "zapisz w pamieci", "to jest wazne")):
        return RouteDecision(IntentType.REMEMBER, RouteType.MEMORY, 0.86, "memory write intent")
    if _contains_any(normalized, ("zapomnij", "usun z pamieci", "nie pamietaj")):
        return RouteDecision(IntentType.FORGET, RouteType.MEMORY, 0.82, "memory delete intent")
    if _contains_any(normalized, ("dokument", "zrodlo", "przeczytaj plik", "pdf", "notatki")):
        return RouteDecision(IntentType.RAG_QUERY, RouteType.RAG, 0.74, "rag intent")
    if tokens & {"zadanie", "zadania", "profil", "projekt", "tryb", "briefing"}:
        return RouteDecision(IntentType.TOOL, RouteType.TOOL, 0.72, "tool-capable intent")

    return RouteDecision(IntentType.LLM, RouteType.LLM, 0.5, "general conversation")


def _contains_any(normalized: str, phrases: tuple[str, ...]) -> bool:
    padded = f" {normalized} "
    return any(f" {normalize_voice_command(phrase)} " in padded for phrase in phrases)
