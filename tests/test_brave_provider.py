import pytest

from src.retrieval.brave_provider import BraveProvider
from src.retrieval.models import QueryPlan, RetrievalError, SearchMode


def _plan():
    return QueryPlan(
        original_question="najnowsza wersja FastAPI",
        needs_realtime=True,
        mode=SearchMode.SOFTWARE,
        search_queries=["FastAPI latest release"],
        preferred_sources=[],
        reason="test",
    )


class _FakeResponse:
    def __init__(self, status_code=200, payload=None):
        self.status_code = status_code
        self._payload = payload or {}

    def json(self):
        return self._payload


def test_brave_provider_brak_api_key():
    with pytest.raises(RetrievalError, match="BRAVE_SEARCH_API_KEY"):
        BraveProvider(api_key=None).search(_plan())


def test_brave_provider_http_429():
    class FakeClient:
        def get(self, *_args, **_kwargs):
            return _FakeResponse(status_code=429)

    with pytest.raises(RetrievalError, match="429"):
        BraveProvider(api_key="key", client=FakeClient()).search(_plan())


def test_brave_provider_mapuje_wyniki():
    class FakeClient:
        def get(self, *_args, **_kwargs):
            return _FakeResponse(
                payload={
                    "web": {
                        "results": [
                            {
                                "title": "FastAPI release",
                                "url": "https://github.com/fastapi/fastapi/releases",
                                "description": "Latest release notes.",
                                "thumbnail": {"src": "https://example.com/fastapi.png"},
                            }
                        ]
                    }
                }
            )

    results = BraveProvider(api_key="key", client=FakeClient()).search(_plan())

    assert results[0].title == "FastAPI release"
    assert results[0].provider == "brave"
    assert results[0].image_url == "https://example.com/fastapi.png"
