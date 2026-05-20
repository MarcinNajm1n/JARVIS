from __future__ import annotations

import re
from dataclasses import dataclass
from typing import Callable

from src.config import Settings, load_settings


@dataclass(frozen=True)
class TranscriptCorrection:
    original: str
    corrected: str
    reason: str


@dataclass(frozen=True)
class TranscriptCorrectionResult:
    original_text: str
    corrected_text: str
    corrections: tuple[TranscriptCorrection, ...]
    confidence: float
    needs_confirmation: bool = False

    @property
    def changed(self) -> bool:
        return self.original_text != self.corrected_text


Replacement = tuple[str, str | Callable[[re.Match[str]], str], str]


def lambda_word(
    replacement: str,
    keep_words: set[str],
    keep_original: bool = False,
) -> Callable[[re.Match[str]], str]:
    def replace(match: re.Match[str]) -> str:
        word = match.group(0).lower()
        if keep_original and word in keep_words:
            return match.group(0)
        return replacement

    return replace


class TranscriptCorrector:
    """Conservative cleanup layer for STT text before local commands and LLM."""

    _REPLACEMENTS: tuple[Replacement, ...] = (
        (
            r"(?<!\w)(dżarwis|dzarvis|dżervis|dzervis|dzerwis|jervis|jerwis|jarwis|jarwiz|djarvis|arvis)(?!\w)",
            "jarvis",
            "alias nazwy asystenta",
        ),
        (
            r"(?<!\w)jarvis\s+(?:s[pś]isz|czy\s+s[pś]isz)\??(?!\w)",
            "jarvis \u015bpisz?",
            "fraza aktywacyjna",
        ),
        (
            r"(?<!\w)(wylacz|wyłoncz|wyloncz|wy\u0142acz)\s+si[eę](?!\w)",
            "wy\u0142\u0105cz si\u0119",
            "komenda zamkniecia programu",
        ),
        (
            r"(?<!\w)(przestan|przesta\u0144|stop|koniec|skoncz|sko\u0144cz)(?!\w)",
            lambda_word("przesta\u0144", {"stop", "koniec"}, keep_original=True),
            "komenda przerwania TTS",
        ),
        (
            r"(?<!\w)(function\s+(?:calling|koling)|funkcj(?:a|e|on)\s+(?:calling|koling))(?!\w)",
            "function calling",
            "termin techniczny",
        ),
        (
            r"(?<!\w)(fast\s*api|fastapi)(?!\w)",
            "FastAPI",
            "termin techniczny",
        ),
        (
            r"(?<!\w)(open\s*a\s*i|open\s+ai|openaj)(?!\w)",
            "OpenAI",
            "termin techniczny",
        ),
        (
            r"(?<!\w)(py\s*test|pajtest|pytest)(?!\w)",
            "pytest",
            "termin techniczny",
        ),
        (
            r"(?<!\w)(obsydian|obsidian)(?!\w)",
            "Obsidian",
            "termin techniczny",
        ),
        (
            r"(?<!\w)(l\s*l\s*m|llm)(?!\w)",
            "LLM",
            "termin techniczny",
        ),
        (
            r"(?<!\w)rag(?!\w)",
            "RAG",
            "termin techniczny",
        ),
        (
            r"(?<!\w)conversation\s+engine(?:\.py)?(?!\w)",
            "conversation_engine.py",
            "nazwa pliku",
        ),
        (
            r"(?<!\w)web\s*app(?:\.py)?(?!\w)",
            "web_app.py",
            "nazwa pliku",
        ),
        (
            r"(?<!\w)function\s+tools(?:\.py)?(?!\w)",
            "function_tools.py",
            "nazwa pliku",
        ),
        (
            r"(?<!\w)memory\s+store(?:\.py)?(?!\w)",
            "memory_store.py",
            "nazwa pliku",
        ),
        (
            r"(?<!\w)command\s+handler(?:\.py)?(?!\w)",
            "command_handler.py",
            "nazwa pliku",
        ),
        (
            r"(?<!\w)(dot|kropka|plik)\s+env(?!\w)",
            ".env",
            "nazwa pliku",
        ),
    )

    def __init__(self, settings: Settings | None = None) -> None:
        self.settings = settings or load_settings()

    def correct(self, text: str) -> TranscriptCorrectionResult:
        original = text.strip()
        corrected = " ".join(original.split())
        corrections: list[TranscriptCorrection] = []

        if corrected != original:
            corrections.append(
                TranscriptCorrection(
                    original=original,
                    corrected=corrected,
                    reason="normalizacja spacji",
                )
            )

        for pattern, replacement, reason in self._REPLACEMENTS:
            corrected = self._replace(corrected, pattern, replacement, reason, corrections)

        confidence = 1.0 if not corrections else min(
            0.98,
            max(self.settings.transcript_correction_min_confidence, 0.65)
            + (0.06 * len(corrections)),
        )

        return TranscriptCorrectionResult(
            original_text=original,
            corrected_text=corrected,
            corrections=tuple(corrections),
            confidence=confidence,
        )

    @staticmethod
    def _replace(
        text: str,
        pattern: str,
        replacement: str | Callable[[re.Match[str]], str],
        reason: str,
        corrections: list[TranscriptCorrection],
    ) -> str:
        def replace_match(match: re.Match[str]) -> str:
            found = match.group(0)
            corrected = replacement(match) if callable(replacement) else replacement
            if found != corrected:
                corrections.append(
                    TranscriptCorrection(
                        original=found,
                        corrected=corrected,
                        reason=reason,
                    )
                )
            return corrected

        return re.sub(pattern, replace_match, text, flags=re.IGNORECASE)
