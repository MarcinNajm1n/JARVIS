from __future__ import annotations

import os
from typing import Any

from src.retrieval.models import QueryPlan, RetrievalError, SearchMode, SearchResult
from src.retrieval.source_policy import domains_for_tavily


class TavilyProvider:
    name = "tavily"

    def __init__(
        self,
        api_key: str | None = None,
        timeout_seconds: float = 15.0,
        max_results: int = 6,
        client: Any | None = None,
    ) -> None:
        self.api_key = api_key or os.getenv("TAVILY_API_KEY")
        self.timeout_seconds = timeout_seconds
        self.max_results = max_results
        self._client = client

    def search(self, plan: QueryPlan) -> list[SearchResult]:
        if not self.api_key and self._client is None:
            raise RetrievalError("Brakuje TAVILY_API_KEY dla TavilyProvider.")

        client = self._client or self._build_client()
        results: list[SearchResult] = []
        for query in plan.search_queries[:3]:
            try:
                data = self._call_search(client, query, plan)
            except TimeoutError as error:
                raise RetrievalError(f"Timeout Tavily dla query: {query}") from error
            except RetrievalError:
                raise
            except Exception as error:
                raise RetrievalError(f"Tavily search failed: {error}") from error
            results.extend(_map_results(data, self.name))
            if len(results) >= self.max_results:
                break
        return _dedupe(results)[: self.max_results]

    def _build_client(self) -> Any:
        try:
            from tavily import TavilyClient
        except Exception as error:
            raise RetrievalError("Brakuje pakietu tavily-python. Zainstaluj requirements.txt.") from error
        return TavilyClient(api_key=self.api_key)

    def _call_search(self, client: Any, query: str, plan: QueryPlan) -> dict[str, Any]:
        kwargs: dict[str, Any] = {
            "query": query,
            "max_results": self.max_results,
            "include_answer": False,
            "include_raw_content": False,
            "include_images": True,
        }
        mode = str(plan.mode)
        include_domains, exclude_domains = domains_for_tavily(plan)
        if include_domains:
            kwargs["include_domains"] = include_domains
        if exclude_domains:
            kwargs["exclude_domains"] = exclude_domains
        if mode == SearchMode.HIGH_RISK.value:
            kwargs["search_depth"] = "advanced"
        if mode == SearchMode.NEWS.value:
            kwargs["topic"] = "news"
        elif mode == SearchMode.FINANCE.value:
            kwargs["topic"] = "finance"
        try:
            return client.search(**kwargs)
        except TypeError:
            for key in ("topic", "search_depth", "include_domains", "exclude_domains"):
                kwargs.pop(key, None)
            return client.search(**kwargs)


def _map_results(data: dict[str, Any], provider: str) -> list[SearchResult]:
    mapped = []
    image_by_url = _image_lookup(data)
    for item in data.get("results") or []:
        title = str(item.get("title") or "").strip()
        url = str(item.get("url") or "").strip()
        if not title or not url:
            continue
        mapped.append(
            SearchResult(
                title=title,
                url=url,
                snippet=item.get("content") or item.get("snippet"),
                provider=provider,
                published_at=item.get("published_date") or item.get("published_at"),
                score=_float_or_none(item.get("score")),
                image_url=item.get("image_url") or image_by_url.get(url),
            )
        )
    return mapped


def _image_lookup(data: dict[str, Any]) -> dict[str, str]:
    lookup: dict[str, str] = {}
    for item in data.get("images") or []:
        if isinstance(item, str):
            continue
        url = str(item.get("url") or item.get("source_url") or "").strip()
        image = str(item.get("image_url") or item.get("url") or "").strip()
        if url and image:
            lookup[url] = image
    return lookup


def _float_or_none(value: Any) -> float | None:
    try:
        return float(value)
    except (TypeError, ValueError):
        return None


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
