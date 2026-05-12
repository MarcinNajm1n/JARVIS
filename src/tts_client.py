from pathlib import Path

import pygame
from openai import OpenAI, OpenAIError

from config import MODEL_TTS, GLOS_TTS, SCIEZKA_PLIKU_AUDIO
from src.llm_client import pobierz_klucz_api
from src.debug_utils import debug_print


def utworz_klienta_openai_tts() -> OpenAI:
    return OpenAI(
        api_key=pobierz_klucz_api()
    )


def generuj_mowe(
    tekst: str,
    sciezka_pliku: str = SCIEZKA_PLIKU_AUDIO
) -> Path | None:
    if tekst.strip() == "":
        return None

    sciezka = Path(sciezka_pliku)
    sciezka.parent.mkdir(parents=True, exist_ok=True)

    try:
        client = utworz_klienta_openai_tts()

        debug_print(f"Generuję TTS modelem: {MODEL_TTS}")
        debug_print(f"Głos TTS: {GLOS_TTS}")
        debug_print(f"Plik audio: {sciezka}")

        with client.audio.speech.with_streaming_response.create(
            model=MODEL_TTS,
            voice=GLOS_TTS,
            input=tekst,
            instructions="Mów po polsku, spokojnie, technicznie i rzeczowo."
        ) as response:
            response.stream_to_file(sciezka)

        return sciezka

    except OpenAIError as blad:
        print(f"Wystąpił błąd po stronie OpenAI TTS API: {blad}")
        return None

    except Exception as blad:
        print(f"Wystąpił nieoczekiwany błąd TTS: {blad}")
        return None


def odtworz_audio(sciezka_pliku: Path) -> None:
    if not sciezka_pliku.exists():
        print("Nie znaleziono pliku audio.")
        return

    pygame.mixer.init()
    pygame.mixer.music.load(str(sciezka_pliku))
    pygame.mixer.music.play()

    while pygame.mixer.music.get_busy():
        pygame.time.Clock().tick(10)

    pygame.mixer.quit()


def powiedz(tekst: str) -> None:
    sciezka = generuj_mowe(tekst)

    if sciezka is None:
        return

    odtworz_audio(sciezka)