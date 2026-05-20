from dataclasses import replace

from src.config import load_settings
from src.transcript_corrector import TranscriptCorrector


def test_transcript_corrector_poprawia_slownik_projektu_i_fraze_wake():
    corrector = TranscriptCorrector(load_settings())

    result = corrector.correct(
        "Dżarwis spisz sprawdz fast api i funkcjon koling w open ai"
    )

    assert result.corrected_text.startswith("jarvis śpisz?")
    assert "FastAPI" in result.corrected_text
    assert "function calling" in result.corrected_text
    assert "OpenAI" in result.corrected_text
    assert result.changed
    assert result.confidence >= 0.65
    assert result.corrections


def test_transcript_corrector_poprawia_nazwy_plikow_i_technologie():
    corrector = TranscriptCorrector(load_settings())

    result = corrector.correct(
        "sprawdz conversation engine oraz web app w obsydian i py test"
    )

    assert "conversation_engine.py" in result.corrected_text
    assert "web_app.py" in result.corrected_text
    assert "Obsidian" in result.corrected_text
    assert "pytest" in result.corrected_text


def test_transcript_corrector_nie_zgaduje_ryzykownie_sensu():
    corrector = TranscriptCorrector(load_settings())

    result = corrector.correct("sprawdz rak w dokumentach")

    assert "RAG" not in result.corrected_text
    assert result.corrected_text == "sprawdz rak w dokumentach"


def test_transcript_corrector_respektuje_minimalna_pewnosc_z_konfiguracji():
    settings = replace(load_settings(), transcript_correction_min_confidence=0.8)
    corrector = TranscriptCorrector(settings)

    result = corrector.correct("open ai")

    assert result.corrected_text == "OpenAI"
    assert result.confidence >= 0.8
