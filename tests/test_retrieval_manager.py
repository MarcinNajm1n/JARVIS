from types import SimpleNamespace

from src.retrieval.manager import RetrievalManager, build_realtime_llm_prompt
from src.retrieval.models import EvidenceChunk, FetchedSource, QueryPlan, RetrievalError, SearchMode, SearchResult


class Settings:
    tavily_api_key = "tavily-key"
    brave_search_api_key = "brave-key"
    web_search_api_key = None
    jarvis_search_timeout_seconds = 1.0
    jarvis_fetch_timeout_seconds = 1.0
    jarvis_search_max_results = 4
    jarvis_rerank_top_k = 2
    jarvis_cache_dir = None
    jarvis_timezone = "Europe/Warsaw"
    jarvis_enable_realtime_search = True
    jarvis_enable_brave_fallback = True
    strict_retrieval = True
    retrieval_trace_path = None


class FakeTavily:
    def __init__(self, results=None, error=None):
        self.results = results or []
        self.error = error

    def search(self, plan):
        if self.error:
            raise self.error
        return self.results


class FakeBrave(FakeTavily):
    pass


class FakeFetcher:
    def __init__(self):
        self.fetched_urls = []

    def fetch_many(self, results, plan):
        self.fetched_urls.extend(result.url for result in results)
        return [
            FetchedSource(
                title=result.title,
                url=result.url,
                provider=result.provider,
                extracted_text=(result.snippet or "OpenAI aktualne informacje. ") * 8,
                trust_score=0.86,
            )
            for result in results
        ]


class FakeEvidenceBuilder:
    def build(self, question, fetched_sources, top_k=5):
        return [
            EvidenceChunk(
                source_url=source.url,
                source_title=source.title,
                text=source.extracted_text or source.raw_snippet or "verified",
                relevance_score=0.9,
                trust_score=source.trust_score,
            )
            for source in fetched_sources
            if not source.fetch_error
        ]


def test_retrieval_manager_tavily_to_evidence_to_prompt():
    fetcher = FakeFetcher()
    manager = RetrievalManager(
        Settings,
        tavily_provider=FakeTavily(
            [
                SearchResult(
                    title="OpenAI news",
                    url="https://openai.com/news",
                    snippet="OpenAI opublikowalo nowe informacje.",
                    provider="tavily",
                    image_url="https://example.com/openai.png",
                )
            ]
        ),
        brave_provider=FakeBrave(),
        fetcher=fetcher,
        cache=None,
    )

    result = manager.retrieve("co najnowszego wiadomo o OpenAI?")
    prompt = build_realtime_llm_prompt("co najnowszego wiadomo o OpenAI?", result)

    assert result.has_evidence is True
    assert result.used_fallback is False
    assert result.visual_assets[0]["url"] == "https://example.com/openai.png"
    assert "Zwroc wylacznie JSON" in prompt
    assert "OpenAI news" in prompt


def test_retrieval_manager_tavily_fail_brave_fallback():
    manager = RetrievalManager(
        Settings,
        tavily_provider=FakeTavily(error=RetrievalError("tavily timeout")),
        brave_provider=FakeBrave(
            [
                SearchResult(
                    title="FastAPI release",
                    url="https://github.com/fastapi/fastapi/releases",
                    snippet="FastAPI release notes.",
                    provider="brave",
                )
            ]
        ),
        fetcher=FakeFetcher(),
        cache=None,
    )

    result = manager.retrieve("jaka jest najnowsza wersja FastAPI")

    assert result.used_fallback is True
    assert result.has_evidence is True
    assert any(operation.name == "FALLBACK_BRAVE" for operation in result.operations)


def test_retrieval_manager_odrzuca_sociale_i_uzywa_brave_przy_slabej_jakosci():
    fetcher = FakeFetcher()
    manager = RetrievalManager(
        Settings,
        tavily_provider=FakeTavily(
            [
                SearchResult(
                    title="Facebook post",
                    url="https://www.facebook.com/historia/posts/123",
                    snippet="post o prezydencie",
                    provider="tavily",
                ),
                SearchResult(
                    title="Reddit trivia",
                    url="https://www.reddit.com/r/todayilearned/comments/123",
                    snippet="dyskusja",
                    provider="tavily",
                ),
            ]
        ),
        brave_provider=FakeBrave(
            [
                SearchResult(
                    title="The White House",
                    url="https://www.whitehouse.gov/administration/",
                    snippet="Official administration page.",
                    provider="brave",
                ),
                SearchResult(
                    title="USA.gov",
                    url="https://www.usa.gov/presidents",
                    snippet="Official information about the president.",
                    provider="brave",
                ),
            ]
        ),
        fetcher=fetcher,
        evidence_builder=FakeEvidenceBuilder(),
        cache=None,
    )

    result = manager.retrieve("Kto jest obecnie prezydentem Stanow Zjednoczonych?")

    assert result.used_fallback is True
    assert result.has_evidence is True
    assert "facebook.com" not in " ".join(fetcher.fetched_urls)
    assert "reddit.com" not in " ".join(fetcher.fetched_urls)
    assert any(item["status"] == "rejected_social" for item in result.rejected_results)


def test_retrieval_manager_bez_brave_nie_zgaduje_z_facebooka():
    class NoFallbackSettings(Settings):
        jarvis_enable_brave_fallback = False

    fetcher = FakeFetcher()
    manager = RetrievalManager(
        NoFallbackSettings,
        tavily_provider=FakeTavily(
            [
                SearchResult(
                    title="Facebook post",
                    url="https://www.facebook.com/historia/posts/123",
                    snippet="post o prezydencie",
                    provider="tavily",
                )
            ]
        ),
        brave_provider=FakeBrave(),
        fetcher=fetcher,
        evidence_builder=FakeEvidenceBuilder(),
        cache=None,
    )

    result = manager.retrieve("Kto jest obecnie prezydentem Stanow Zjednoczonych?")

    assert result.has_evidence is False
    assert fetcher.fetched_urls == []
    assert result.fallback_answer().confidence == "low"


def test_retrieval_manager_obaj_providerzy_fail_low_confidence():
    manager = RetrievalManager(
        Settings,
        tavily_provider=FakeTavily(error=RetrievalError("tavily down")),
        brave_provider=FakeBrave(error=RetrievalError("brave down")),
        fetcher=FakeFetcher(),
        cache=None,
    )

    result = manager.retrieve("co sie dzisiaj wydarzylo w OpenAI?")
    answer = result.fallback_answer()

    assert result.has_evidence is False
    assert answer.confidence == "low"
    assert "wiarygodnie" in answer.spoken_answer


def test_retrieval_manager_cacheuje_pobrane_strony():
    class MemoryCache:
        def __init__(self):
            self.data = {}

        def get(self, key):
            return self.data.get(key)

        def set(self, key, value, expire=None):
            self.data[key] = value

    class CountingFetcher(FakeFetcher):
        def __init__(self):
            super().__init__()
            self.calls = 0

        def fetch_many(self, results, plan):
            self.calls += 1
            return super().fetch_many(results, plan)

    fetcher = CountingFetcher()
    cache = MemoryCache()
    manager = RetrievalManager(
        Settings,
        tavily_provider=FakeTavily(
            [
                SearchResult(
                    title="FastAPI release",
                    url="https://github.com/fastapi/fastapi/releases",
                    snippet="FastAPI release notes.",
                    provider="tavily",
                )
            ]
        ),
        brave_provider=FakeBrave(),
        fetcher=fetcher,
        cache=cache,
    )

    manager.retrieve("jaka jest wersja release FastAPI")
    manager.retrieve("jaka jest wersja release FastAPI")

    assert fetcher.calls == 1
    assert any(key.startswith("fetch-v1:") for key in cache.data)
