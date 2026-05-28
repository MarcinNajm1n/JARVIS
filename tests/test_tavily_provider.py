import pytest

from src.retrieval.models import QueryPlan, RetrievalError, SearchMode
from src.retrieval.tavily_provider import TavilyProvider


def _plan():
    return QueryPlan(
        original_question="co najnowszego wiadomo o OpenAI",
        needs_realtime=True,
        mode=SearchMode.NEWS,
        search_queries=["OpenAI latest news"],
        preferred_sources=[],
        reason="test",
    )


def test_tavily_provider_brak_api_key_daje_czytelny_blad(monkeypatch):
    monkeypatch.delenv("TAVILY_API_KEY", raising=False)

    with pytest.raises(RetrievalError, match="TAVILY_API_KEY"):
        TavilyProvider(api_key=None).search(_plan())


def test_tavily_provider_timeout_mapowany_na_kontrolowany_blad():
    class FakeClient:
        def search(self, **_kwargs):
            raise TimeoutError("boom")

    with pytest.raises(RetrievalError, match="Timeout Tavily"):
        TavilyProvider(api_key="key", client=FakeClient()).search(_plan())


def test_tavily_provider_mapuje_poprawna_odpowiedz():
    class FakeClient:
        def search(self, **_kwargs):
            return {
                "results": [
                    {
                        "title": "OpenAI update",
                        "url": "https://openai.com/news",
                        "content": "Nowe informacje.",
                        "score": 0.91,
                        "published_date": "2026-05-21",
                    }
                ]
            }

    results = TavilyProvider(api_key="key", client=FakeClient()).search(_plan())

    assert results[0].title == "OpenAI update"
    assert results[0].provider == "tavily"
    assert results[0].score == 0.91


def test_tavily_provider_przekazuje_include_exclude_domains_dla_high_risk():
    captured = {}

    class FakeClient:
        def search(self, **kwargs):
            captured.update(kwargs)
            return {"results": []}

    plan = QueryPlan(
        original_question="Kto jest prezydentem Stanow Zjednoczonych?",
        needs_realtime=True,
        mode=SearchMode.HIGH_RISK,
        search_queries=["current president site:whitehouse.gov"],
        required_domains=["whitehouse.gov", "usa.gov"],
        excluded_domains=["facebook.com"],
        reason="test",
    )

    TavilyProvider(api_key="key", client=FakeClient()).search(plan)

    assert captured["include_domains"] == ["whitehouse.gov", "usa.gov"]
    assert "facebook.com" in captured["exclude_domains"]
    assert captured["search_depth"] == "advanced"
