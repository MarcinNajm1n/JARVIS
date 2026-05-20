from __future__ import annotations

import json
import re
import urllib.parse
import urllib.request
from dataclasses import dataclass, field
from typing import Any


DUCKDUCKGO_URL = "https://api.duckduckgo.com/"
WIKIPEDIA_SEARCH_URL = "https://pl.wikipedia.org/w/api.php"


@dataclass(frozen=True)
class SearchResult:
    title: str
    url: str
    snippet: str = ""
    image_url: str | None = None
    source: str = "web"

    def as_dict(self) -> dict[str, Any]:
        return {
            "title": self.title,
            "url": self.url,
            "snippet": self.snippet,
            "image_url": self.image_url,
            "source": self.source,
        }


@dataclass(frozen=True)
class WebSearchBundle:
    query: str
    results: list[SearchResult] = field(default_factory=list)
    source: str = "web"

    @property
    def best(self) -> SearchResult | None:
        return self.results[0] if self.results else None

    def as_payload_results(self, limit: int = 4) -> list[dict[str, Any]]:
        return [result.as_dict() for result in self.results[:limit]]


def search_web(query: str, timeout: float = 4.0, limit: int = 4) -> WebSearchBundle:
    clean_query = _clean_query(query)
    if not clean_query:
        return WebSearchBundle(query=query, results=[], source="web")

    results: list[SearchResult] = []
    results.extend(_search_duckduckgo(clean_query, timeout=timeout))
    results.extend(_search_wikipedia(clean_query, timeout=timeout))
    return WebSearchBundle(
        query=clean_query,
        results=_dedupe_results(results)[:limit],
        source="DuckDuckGo/Wikipedia",
    )


def _search_duckduckgo(query: str, timeout: float) -> list[SearchResult]:
    params = urllib.parse.urlencode(
        {
            "q": query,
            "format": "json",
            "no_redirect": 1,
            "no_html": 1,
            "skip_disambig": 1,
        }
    )
    try:
        data = _fetch_json(f"{DUCKDUCKGO_URL}?{params}", timeout=timeout)
    except Exception:
        return []

    results: list[SearchResult] = []
    abstract = str(data.get("AbstractText") or "").strip()
    title = str(data.get("Heading") or "").strip()
    url = str(data.get("AbstractURL") or "").strip()
    image = _absolute_duckduckgo_image(data.get("Image"))
    if title and url:
        results.append(
            SearchResult(
                title=title,
                url=url,
                snippet=abstract,
                image_url=image,
                source="DuckDuckGo",
            )
        )

    for item in _flatten_related_topics(data.get("RelatedTopics") or []):
        text = str(item.get("Text") or "").strip()
        first_url = str(item.get("FirstURL") or "").strip()
        icon = item.get("Icon") or {}
        icon_url = _absolute_duckduckgo_image(icon.get("URL"))
        if text and first_url:
            results.append(
                SearchResult(
                    title=_title_from_related_text(text),
                    url=first_url,
                    snippet=text,
                    image_url=icon_url,
                    source="DuckDuckGo",
                )
            )
    return results


def _search_wikipedia(query: str, timeout: float) -> list[SearchResult]:
    params = urllib.parse.urlencode(
        {
            "action": "query",
            "list": "search",
            "srsearch": query,
            "srlimit": 3,
            "format": "json",
            "utf8": 1,
        }
    )
    try:
        data = _fetch_json(f"{WIKIPEDIA_SEARCH_URL}?{params}", timeout=timeout)
    except Exception:
        return []

    results = []
    for item in ((data.get("query") or {}).get("search") or []):
        title = str(item.get("title") or "").strip()
        if not title:
            continue
        snippet = re.sub(r"<[^>]+>", "", str(item.get("snippet") or "")).strip()
        url_title = urllib.parse.quote(title.replace(" ", "_"))
        results.append(
            SearchResult(
                title=title,
                url=f"https://pl.wikipedia.org/wiki/{url_title}",
                snippet=snippet,
                source="Wikipedia",
            )
        )
    return results


def _fetch_json(url: str, timeout: float) -> dict[str, Any]:
    request = urllib.request.Request(url, headers={"User-Agent": "JARVIS-local-ui/1.0"})
    with urllib.request.urlopen(request, timeout=timeout) as response:
        return json.loads(response.read().decode("utf-8"))


def _flatten_related_topics(items: list[dict[str, Any]]) -> list[dict[str, Any]]:
    flattened = []
    for item in items:
        if "Topics" in item:
            flattened.extend(_flatten_related_topics(item.get("Topics") or []))
        else:
            flattened.append(item)
    return flattened


def _absolute_duckduckgo_image(value: Any) -> str | None:
    image = str(value or "").strip()
    if not image:
        return None
    if image.startswith("//"):
        return f"https:{image}"
    if image.startswith("/"):
        return f"https://duckduckgo.com{image}"
    return image


def _title_from_related_text(text: str) -> str:
    return text.split(" - ", 1)[0].split(",", 1)[0][:90].strip() or "Wynik"


def _dedupe_results(results: list[SearchResult]) -> list[SearchResult]:
    seen = set()
    unique = []
    for result in results:
        key = (result.title.lower(), result.url.lower())
        if key in seen:
            continue
        seen.add(key)
        unique.append(result)
    return unique


def _clean_query(query: str) -> str:
    return re.sub(r"\s+", " ", query or "").strip(" ?!.,;:")
