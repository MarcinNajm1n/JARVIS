from pathlib import Path

from src.research_orchestrator import build_research_brief
from src.web_search import SearchResult, WebSearchBundle


class Settings:
    web_search_enabled = True
    web_search_provider = "fake"
    web_search_timeout = 3.0
    web_search_cache_enabled = False
    web_search_cache_path = Path("unused")
    research_trace_path = None
    llm_validator_enabled = False
    llm_validator_model = "gpt-4.1-mini"
    llm_validator_min_confidence = 0.72


def test_research_orchestrator_buduje_display_z_walidowanymi_mediami():
    bundle = WebSearchBundle(
        query="Elon Musk",
        results=[
            SearchResult(
                title="Elon Musk",
                url="https://example.com/elon",
                snippet="Elon Musk jest przedsiebiorca i prowadzi firmy technologiczne.",
                image_url="https://upload.wikimedia.org/elon.jpg",
                source="Wikipedia",
                confidence=0.86,
            ),
            SearchResult(
                title="Elon Musk documentary video",
                url="https://youtube.com/watch?v=elon",
                snippet="Video o Elon Musk.",
                source="YouTube",
                confidence=0.78,
            ),
            SearchResult(
                title="Elon Musk report PDF",
                url="https://university.edu/elon-musk.pdf",
                snippet="Research report about Elon Musk companies.",
                source="University",
                confidence=0.74,
            ),
            SearchResult(
                title="Hansi Flick",
                url="https://example.com/hansi",
                snippet="Hansi Flick jest trenerem pilkarskim.",
                image_url="https://example.com/hansi.jpg",
                source="Wikipedia",
                confidence=0.9,
            ),
        ],
    )

    payload = build_research_brief(
        "kto jest najbogatszy na swiecie",
        "Elon Musk jest obecnie jedna z najbogatszych osob na swiecie.",
        search_bundle=bundle,
        settings=Settings,
    )

    assert payload is not None
    assert payload["mode"] == "research_brief"
    assert payload["topic"] == "Elon Musk"
    assert payload["images"][0]["image_url"].endswith("elon.jpg")
    assert payload["media_items"][0]["fit"] == "contain"
    assert payload["media_items"][0]["cropping_allowed"] is False
    assert all("hansi" not in image["image_url"].lower() for image in payload["images"])
    assert payload["reports"][0]["url"].endswith(".pdf")
    assert payload["videos"][0]["url"].startswith("https://youtube.com")
    assert payload["validation"]["status"] == "supported"
    assert payload["planner_trace"]["topic"] == "Elon Musk"


def test_research_orchestrator_nie_pokazuje_displaya_gdy_search_nie_pokrywa_sie_z_odpowiedzia():
    bundle = WebSearchBundle(
        query="najbogatszy czlowiek",
        results=[
            SearchResult(
                title="Hansi Flick",
                url="https://example.com/hansi",
                snippet="Hansi Flick jest trenerem pilkarskim.",
                image_url="https://example.com/hansi.jpg",
                confidence=0.9,
            )
        ],
    )

    payload = build_research_brief(
        "Pokaz mi, kto jest najbogatszym czlowiekiem na swiecie.",
        "Wedlug rankingu Elon Musk jest obecnie najbogatszym czlowiekiem na swiecie.",
        search_bundle=bundle,
        settings=Settings,
        search_provider=lambda query, timeout, limit: bundle,
    )

    assert payload is None
