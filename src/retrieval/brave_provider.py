from __future__ import annotations

import os
from typing import Any

import httpx

from src.retrieval.models import QueryPlan, RetrievalError, SearchResult


BRAVE_SEARCH_URL = "https://api.search.brave.com/res/v1/web/search"


class BraveProvider:
    name = "brave"

    def __init__(
        self,
        api_key: str | None = None,
        timeout_seconds: float = 15.0,
        max_results: int = 6,
        client: httpx.Client | None = None,
    ) -> None:
        self.api_key = api_key or os.getenv("BRAVE_SEARCH_API_KEY")
        self.timeout_seconds = timeout_seconds
        self.max_results = max_results
        self._client = client

    def search(self, plan: QueryPlan) -> list[SearchResult]:
        if not self.api_key:
            raise RetrievalError("Brakuje BRAVE_SEARCH_API_KEY dla BraveProvider.")

        results: list[SearchResult] = []
        for query in plan.search_queries[:3]:
            data = self._request(query)
            results.extend(_map_results(data, self.name))
            if len(results) >= self.max_results:
                break
        return _dedupe(results)[: self.max_results]

    def _request(self, query: str) -> dict[str, Any]:
        headers = {
            "Accept": "application/json",
            "X-Subscription-Token": self.api_key or "",
            "Cache-Control": "no-cache",
            "User-Agent": "JarvisBot/1.0",
        }
        params = {"q": query, "count": min(max(self.max_results, 1), 20)}
        try:
            if self._client is not None:
                response = self._client.get(BRAVE_SEARCH_URL, params=params, headers=headers)
            else:
                with httpx.Client(timeout=self.timeout_seconds, follow_redirects=True) as client:
                    response = client.get(BRAVE_SEARCH_URL, params=params, headers=headers)
        except httpx.TimeoutException as error:
            raise RetrievalError("Timeout Brave Search.") from error
        except httpx.HTTPError as error:
            raise RetrievalError(f"Blad HTTP Brave Search: {error}") from error

        if response.status_code == 429:
            raise RetrievalError("Brave Search rate limit HTTP 429.", rate_limited=True)
        if response.status_code >= 400:
            raise RetrievalError(f"Brave Search HTTP {response.status_code}.")
        return response.json()


def _map_results(data: dict[str, Any], provider: str) -> list[SearchResult]:
    mapped = []
    for item in (data.get("web") or {}).get("results") or []:
        title = str(item.get("title") or "").strip()
        url = str(item.get("url") or "").strip()
        if not title or not url:
            continue
        thumbnail = item.get("thumbnail") if isinstance(item.get("thumbnail"), dict) else {}
        mapped.append(
            SearchResult(
                title=title,
                url=url,
                snippet=item.get("description"),
                provider=provider,
                published_at=item.get("age") or item.get("page_age"),
                score=None,
                image_url=thumbnail.get("src"),
            )
        )
    return mapped


def _dedupe(results: list[SearchResult]) -> list[SearchResult]:
    seen = set()
    unique = []
    for result in results:
        key = result.url.lower()
        if key in seen:
            continue
        seen.add(key)
        unique.append(result)
    return unique
