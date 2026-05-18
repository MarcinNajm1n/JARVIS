from __future__ import annotations

from pathlib import Path

from src.tts import TextToSpeechClient


def generuj_mowe(tekst: str, sciezka_pliku: str | None = None) -> Path | None:
    client = TextToSpeechClient()
    output_path = Path(sciezka_pliku) if sciezka_pliku else None
    return client.generate_speech(tekst, output_path)


def odtworz_audio(sciezka_pliku: Path) -> None:
    TextToSpeechClient().play_audio(sciezka_pliku)


def powiedz(tekst: str) -> None:
    TextToSpeechClient().speak(tekst)
