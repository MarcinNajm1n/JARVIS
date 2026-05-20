from __future__ import annotations

import re
import unicodedata


ASSISTANT_NAME_ALIASES = {
    "jarvis",
    "jarwis",
    "jarwiz",
    "jervis",
    "jerwis",
    "dzarvis",
    "dzervis",
    "dzerwis",
    "djarvis",
    "arvis",
}

TTS_STOP_COMMANDS = {
    "stop",
    "jarvis stop",
    "przestan",
    "przestan mowic",
    "przerwij",
    "przerwij mowienie",
    "koniec",
    "skoncz",
    "cisza",
}

ACTIVATION_PHRASES = {
    "jarvis spisz",
    "jarvis czy spisz",
    "jarvis aktywacja",
    "jarvis aktywuj sie",
    "jarvis obudz sie",
    "jarvis wroc",
    "jarvis online",
    "jarvis sluchaj",
    "hej jarvis",
    "ej jarvis",
    "jarvis jestes",
    "jarvis jestes tam",
}

ACTIVATION_TERMS = {
    "aktywacja",
    "aktywuj",
    "aktywny",
    "obudz",
    "wroc",
    "online",
    "start",
    "sluchaj",
    "sluchasz",
}

SHUTDOWN_PHRASES = {
    "jarvis wylacz sie",
    "jarvis wy cz si",
    "jarvis wylacz",
    "jarvis dezaktywacja",
    "jarvis dezaktywuj sie",
    "jarvis zakoncz",
    "jarvis zakoncz prace",
    "jarvis zamknij sie",
    "jarvis zamknij program",
    "jarvis zamknij aplikacje",
    "jarvis koniec pracy",
    "jarvis idz spac",
    "jarvis dobranoc",
    "jarvis offline",
    "wylacz sie",
    "wylacz program",
    "wy cz program",
    "wylacz aplikacje",
    "zakoncz program",
    "zakoncz dzialanie",
    "zamknij program",
    "zamknij aplikacje",
    "koniec pracy",
}

SHUTDOWN_TERMS = {
    "wylacz",
    "dezaktywacja",
    "dezaktywuj",
    "zakoncz",
    "zamknij",
    "offline",
    "dobranoc",
}

PROGRAM_TERMS = {
    "sie",
    "program",
    "aplikacje",
    "aplikacja",
    "dzialanie",
    "prace",
    "system",
}


def is_tts_stop_command(text: str) -> bool:
    normalized = normalize_voice_command(text)
    return normalized in {normalize_voice_command(command) for command in TTS_STOP_COMMANDS}


def is_activation_command(text: str) -> bool:
    normalized = normalize_voice_command(text)
    if not normalized:
        return False

    if _contains_any_phrase(normalized, ACTIVATION_PHRASES):
        return True

    tokens = normalized.split()
    if not _has_assistant_reference(tokens):
        return False

    return any(token in ACTIVATION_TERMS for token in tokens)


def is_shutdown_command(text: str) -> bool:
    normalized = normalize_voice_command(text)
    if not normalized:
        return False

    if _contains_any_phrase(normalized, SHUTDOWN_PHRASES):
        return True

    tokens = normalized.split()
    has_assistant = _has_assistant_reference(tokens)
    has_shutdown_term = any(token in SHUTDOWN_TERMS for token in tokens)
    has_program_target = any(token in PROGRAM_TERMS for token in tokens)

    return has_shutdown_term and (has_assistant or has_program_target)


def normalize_voice_command(text: str) -> str:
    text = text.strip().lower()
    text = unicodedata.normalize("NFKD", text)
    text = "".join(character for character in text if not unicodedata.combining(character))
    text = re.sub(r"[^a-z0-9 ]+", " ", text)
    return " ".join(text.split())


def _has_assistant_reference(tokens: list[str]) -> bool:
    return any(token in ASSISTANT_NAME_ALIASES for token in tokens)


def _contains_any_phrase(normalized_text: str, phrases: set[str]) -> bool:
    padded_text = f" {normalized_text} "
    return any(f" {normalize_voice_command(phrase)} " in padded_text for phrase in phrases)
