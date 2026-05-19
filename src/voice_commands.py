from __future__ import annotations

import re
import unicodedata


TTS_STOP_COMMANDS = {
    "stop",
    "jarvis stop",
    "przestan",
    "przestań",
    "koniec",
    "skoncz",
    "skończ",
    "cisza",
}

SHUTDOWN_COMMANDS = {
    "jarvis wylacz sie",
    "jarvis wyłącz się",
    "wylacz sie",
    "wyłącz się",
    "wylacz program",
    "wyłącz program",
    "zakoncz program",
    "zakończ program",
    "zamknij program",
    "koniec pracy",
}


def is_tts_stop_command(text: str) -> bool:
    normalized = normalize_voice_command(text)
    return normalized in {normalize_voice_command(command) for command in TTS_STOP_COMMANDS}


def is_shutdown_command(text: str) -> bool:
    normalized = normalize_voice_command(text)
    return normalized in {normalize_voice_command(command) for command in SHUTDOWN_COMMANDS}


def normalize_voice_command(text: str) -> str:
    text = text.strip().lower()
    text = unicodedata.normalize("NFKD", text)
    text = "".join(character for character in text if not unicodedata.combining(character))
    text = re.sub(r"[^a-z0-9 ]+", " ", text)
    return " ".join(text.split())
