from src.display import build_display_payload, display
from src.retrieval.models import JarvisAnswer


def test_jarvis_answer_serializuje_sie_do_json_i_payload_ma_operations():
    answer = JarvisAnswer(
        answer="OpenAI oglosilo aktualizacje.",
        spoken_answer="OpenAI oglosilo aktualizacje.",
        confidence="high",
        checked_at="2026-05-21T12:00:00+02:00",
        sources=[{"title": "OpenAI", "url": "https://openai.com", "summary": "news"}],
        operations=[{"name": "SEARCHING_TAVILY", "status": "done", "duration_ms": 20}],
        visual_assets=[],
    )

    payload = build_display_payload(answer, "Co najnowszego wiadomo o OpenAI?")

    assert answer.model_dump_json()
    assert payload["mode"] == "jarvis_tactical_hud"
    assert payload["presentation"] == "animated_scene"
    assert payload["animation_profile"] == "result"
    assert payload["operations"][0]["name"] == "SEARCHING_TAVILY"
    assert payload["visual_assets"] == []
    assert payload["normalized_results"][0]["title"] == "OpenAI"
    assert payload["normalized_results"][0]["url"] == "https://openai.com"


def test_spoken_answer_nie_zawiera_url():
    payload = display(
        {
            "mode": "jarvis_tactical_hud",
            "display_type": "jarvis_tactical_hud",
            "answer": "Pelna odpowiedz: https://example.com",
            "spoken_answer": "Sprawdzilem https://example.com i mam wynik.",
        }
    )

    assert "https://" not in payload["spoken_answer"]


def test_low_confidence_without_sources_gives_neutral_display():
    answer = JarvisAnswer(
        answer="Brak pewnego displaya. Zrodla niewystarczajace.",
        spoken_answer="Nie mam wystarczajaco wiarygodnych danych.",
        confidence="low",
        checked_at="2026-05-21T12:00:00+02:00",
        sources=[],
        visual_assets=[],
    )

    payload = build_display_payload(answer, "Kto jest prezydentem USA?")

    assert payload["ok"] is False
    assert payload["presentation"] == "animated_scene"
    assert payload["animation_profile"] == "low_confidence"
    assert payload["visual_assets"] == []
