from src.search_service import (
    build_search_context,
    requires_current_information,
    score_search_result,
    search_current_information,
    search_current_information_for_question,
    validate_search_results,
)
from src.web_search import SearchResult, WebSearchBundle


def test_requires_current_information_rozpoznaje_aktualne_pytania():
    assert requires_current_information("kto jest teraz najbogatszy na swiecie") is True
    assert requires_current_information("kto jest obecnym CEO OpenAI") is True
    assert requires_current_information("jaka jest dzisiaj cena bitcoina") is True
    assert requires_current_information("ostatnie informacje o Tesli") is True
    assert requires_current_information("jaki jest status projektu") is False


def test_search_current_information_uzywa_cache_i_provider(tmp_path):
    calls = []

    class Settings:
        web_search_enabled = True
        web_search_provider = "fake"
        web_search_timeout = 3.0
        web_search_result_limit = 5
        web_search_cache_enabled = True
        web_search_cache_path = tmp_path / "search_cache.json"
        web_search_cache_ttl_seconds = 900

    def provider(query, timeout, limit):
        calls.append((query, timeout, limit))
        return WebSearchBundle(
            query=query,
            results=[
                SearchResult(
                    title="Elon Musk",
                    url="https://example.com/elon",
                    snippet="Aktualny wynik testowy.",
                    source="Fake",
                    confidence=0.8,
                )
            ],
            source="Fake",
        )

    first = search_current_information("najbogatszy czlowiek", Settings, provider=provider)
    second = search_current_information("najbogatszy czlowiek", Settings, provider=provider)

    assert calls == [("najbogatszy czlowiek", 3.0, 5)]
    assert first.results[0].title == "Elon Musk"
    assert second.results[0].title == "Elon Musk"


def test_search_current_information_for_question_uzywa_planu_forbes(tmp_path):
    calls = []

    class Settings:
        web_search_enabled = True
        web_search_provider = "fake"
        web_search_api_key = None
        web_search_timeout = 3.0
        web_search_result_limit = 5
        web_search_cache_enabled = False
        web_search_cache_path = tmp_path / "search_cache.json"
        web_search_cache_ttl_seconds = 900

    def provider(query, timeout, limit):
        calls.append((query, timeout, limit))
        return WebSearchBundle(
            query=query,
            results=[
                SearchResult(
                    title="Forbes Real-Time Billionaires #1: Elon Musk",
                    url="https://www.forbes.com/real-time-billionaires/",
                    snippet="Forbes Real-Time Billionaires ranks Elon Musk #1.",
                    source="Forbes Real-Time Billionaires",
                    confidence=0.94,
                )
            ],
            source="Fake",
        )

    bundle = search_current_information_for_question(
        "kto jest najbogatszym czlowiekiem na swiecie",
        Settings,
        provider=provider,
    )

    assert calls[0][0].startswith("Forbes Real-Time Billionaires")
    assert bundle.best is not None
    assert bundle.best.title == "Forbes Real-Time Billionaires #1: Elon Musk"


def test_validate_search_results_i_context_formatuja_zrodla():
    bundle = WebSearchBundle(
        query="Elon Musk",
        results=[
            SearchResult(
                title="Elon Musk",
                url="https://example.com/elon",
                snippet="Elon Musk jest wymieniany w rankingu.",
                confidence=0.85,
            )
        ],
    )

    validation = validate_search_results("kto jest najbogatszy", "Elon Musk.", bundle)
    context = build_search_context(bundle)

    assert validation.status == "supported"
    assert validation.best_sources[0]["url"] == "https://example.com/elon"
    assert "Kontekst z aktualnego wyszukiwania" in context
    assert "https://example.com/elon" in context


def test_build_search_context_zawiera_twardy_guardrail_anty_cutoff():
    context = build_search_context(WebSearchBundle(query="kto jest obecnym CEO OpenAI", results=[]))

    assert "Nie korzystaj z wiedzy modelu jako zrodla prawdy" in context
    assert "Nie mow, ze Twoja wiedza siega 2024" in context
    assert "Nie mam wystarczajaco pewnych aktualnych danych" in context


def test_score_search_result_premiuje_autorytet_i_aktualna_date():
    strong = SearchResult(
        title="Elon Musk real time billionaires ranking",
        url="https://www.forbes.com/real-time-billionaires/",
        snippet="Elon Musk appears in the current billionaires ranking.",
        source="Forbes",
        published_at="2026-05-20",
    )
    weak = SearchResult(
        title="Random profile",
        url="https://example-blog.test/random",
        snippet="Old unrelated article.",
        source="Blog",
        published_at="2020-01-01",
    )

    assert score_search_result("kto jest teraz najbogatszy na swiecie Elon Musk", strong, [strong, weak]) > score_search_result(
        "kto jest teraz najbogatszy na swiecie Elon Musk",
        weak,
        [strong, weak],
    )
