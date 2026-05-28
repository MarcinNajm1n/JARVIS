from src.retrieval.fetcher import PageFetcher, extract_text
from src.retrieval.models import QueryPlan, SearchMode, SearchResult


def _plan():
    return QueryPlan(
        original_question="jaka jest najnowsza wersja FastAPI",
        needs_realtime=True,
        mode=SearchMode.SOFTWARE,
        search_queries=["FastAPI release"],
        preferred_sources=[],
        reason="test",
    )


def test_fetcher_trafilatura_success(monkeypatch):
    monkeypatch.setattr("src.retrieval.fetcher._extract_with_trafilatura", lambda html, url: "Tekst z trafilatura.")

    assert extract_text("<html></html>", "https://example.com") == "Tekst z trafilatura."


def test_fetcher_empty_trafilatura_uzywa_bs4_fallback(monkeypatch):
    monkeypatch.setattr("src.retrieval.fetcher._extract_with_trafilatura", lambda html, url: "")

    text = extract_text("<html><body><p>Fallback content.</p></body></html>")

    assert "Fallback content." in text


def test_fetch_error_nie_zabija_buildera(monkeypatch):
    fetcher = PageFetcher()
    result = SearchResult(
        title="FastAPI",
        url="https://fastapi.tiangolo.com",
        snippet="FastAPI docs snippet.",
        provider="test",
    )
    monkeypatch.setattr(fetcher, "_download", lambda _url: (_ for _ in ()).throw(RuntimeError("offline")))

    fetched = fetcher.fetch(result, _plan())

    assert fetched.fetch_error is None
    assert fetched.extracted_text == "FastAPI docs snippet."
    assert fetched.trust_score > 0
