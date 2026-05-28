from __future__ import annotations

import json
import re
import urllib.parse
import urllib.request
from dataclasses import dataclass, field
from datetime import datetime, timezone
from typing import Any


DUCKDUCKGO_URL = "https://api.duckduckgo.com/"
WIKIPEDIA_SEARCH_URL = "https://pl.wikipedia.org/w/api.php"
BRAVE_SEARCH_URL = "https://api.search.brave.com/res/v1/web/search"
FORBES_REALTIME_BILLIONAIRES_URL = "https://www.forbes.com/real-time-billionaires/"


@dataclass(frozen=True)
class SearchResult:
    title: str
    url: str
    snippet: str = ""
    image_url: str | None = None
    source: str = "web"
    published_at: str | None = None
    confidence: float = 0.65

    def as_dict(self) -> dict[str, Any]:
        return {
            "title": self.title,
            "url": self.url,
            "snippet": self.snippet,
            "image_url": self.image_url,
            "source": self.source,
            "published_at": self.published_at,
            "confidence": self.confidence,
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
    results.extend(_search_forbes_realtime_billionaires(clean_query, timeout=timeout))
    results.extend(_search_duckduckgo(clean_query, timeout=timeout))
    results.extend(_search_wikipedia(clean_query, timeout=timeout))
    source = "Forbes/DuckDuckGo/Wikipedia" if any(
        result.source == "Forbes Real-Time Billionaires" for result in results
    ) else "DuckDuckGo/Wikipedia"
    return WebSearchBundle(
        query=clean_query,
        results=_dedupe_results(results)[:limit],
        source=source,
    )


def search_brave(
    query: str,
    api_key: str,
    timeout: float = 4.0,
    limit: int = 8,
) -> WebSearchBundle:
    clean_query = _clean_query(query)
    if not clean_query or not api_key:
        return WebSearchBundle(query=clean_query, results=[], source="Brave")

    params = urllib.parse.urlencode({"q": clean_query, "count": min(max(limit, 1), 20)})
    request = urllib.request.Request(
        f"{BRAVE_SEARCH_URL}?{params}",
        headers={
            "Accept": "application/json",
            "X-Subscription-Token": api_key,
            "User-Agent": "JARVIS-local-ui/1.0",
        },
    )
    try:
        with urllib.request.urlopen(request, timeout=timeout) as response:
            data = json.loads(response.read().decode("utf-8"))
    except Exception:
        return WebSearchBundle(query=clean_query, results=[], source="Brave")

    results = []
    web_results = (data.get("web") or {}).get("results") or []
    for item in web_results:
        title = str(item.get("title") or "").strip()
        url = str(item.get("url") or "").strip()
        snippet = _strip_html(str(item.get("description") or "").strip())
        age = str(item.get("age") or "").strip() or None
        thumbnail = ((item.get("thumbnail") or {}).get("src")) if isinstance(item.get("thumbnail"), dict) else None
        if title and url:
            results.append(
                SearchResult(
                    title=title,
                    url=url,
                    snippet=snippet,
                    image_url=thumbnail,
                    source="Brave",
                    published_at=age,
                    confidence=0.72,
                )
            )
    return WebSearchBundle(query=clean_query, results=_dedupe_results(results)[:limit], source="Brave")


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


def _search_forbes_realtime_billionaires(query: str, timeout: float) -> list[SearchResult]:
    if not _is_richest_person_query(query):
        return []
    try:
        request = urllib.request.Request(
            FORBES_REALTIME_BILLIONAIRES_URL,
            headers={"User-Agent": "Mozilla/5.0 JARVIS-local-ui/1.0"},
        )
        with urllib.request.urlopen(request, timeout=timeout) as response:
            html = response.read().decode("utf-8", "ignore")
    except Exception:
        return []

    data = _extract_next_data(html)
    billionaires = _find_key_recursively(data, "billionaires")
    if not isinstance(billionaires, list) or not billionaires:
        return []

    top = None
    for item in billionaires:
        if not isinstance(item, dict):
            continue
        if int(item.get("rank") or item.get("position") or 999999) == 1:
            top = item
            break
    top = top or next((item for item in billionaires if isinstance(item, dict)), None)
    if not top:
        return []

    name = str(top.get("personName") or "").strip()
    if not name:
        return []
    source = str(top.get("source") or "").strip()
    worth = _format_forbes_worth(top.get("finalWorth"))
    timestamp = _timestamp_to_date(top.get("timestamp"))
    image_url = top.get("squareImage") or top.get("personSquareImage")
    snippet = f"Forbes Real-Time Billionaires ranks {name} #1"
    if worth:
        snippet += f" with estimated net worth {worth}"
    if source:
        snippet += f"; source of wealth: {source}"
    return [
        SearchResult(
            title=f"Forbes Real-Time Billionaires #1: {name}",
            url=FORBES_REALTIME_BILLIONAIRES_URL,
            snippet=snippet + ".",
            image_url=str(image_url).strip() if image_url else None,
            source="Forbes Real-Time Billionaires",
            published_at=timestamp,
            confidence=0.94,
        )
    ]


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


def _extract_next_data(html: str) -> dict[str, Any]:
    match = re.search(
        r'<script id="__NEXT_DATA__" type="application/json">(.*?)</script>',
        html,
        flags=re.DOTALL,
    )
    if not match:
        return {}
    try:
        return json.loads(match.group(1))
    except Exception:
        return {}


def _find_key_recursively(data: Any, target_key: str) -> Any:
    if isinstance(data, dict):
        if target_key in data:
            return data[target_key]
        for value in data.values():
            found = _find_key_recursively(value, target_key)
            if found is not None:
                return found
    if isinstance(data, list):
        for item in data:
            found = _find_key_recursively(item, target_key)
            if found is not None:
                return found
    return None


def _is_richest_person_query(query: str) -> bool:
    normalized = _normalize_ascii(query)
    return (
        ("najbogatsz" in normalized and ("swiecie" in normalized or "czlowiek" in normalized))
        or ("richest" in normalized and ("person" in normalized or "people" in normalized))
        or ("billionaires" in normalized and ("forbes" in normalized or "ranking" in normalized))
    )


def _format_forbes_worth(value: Any) -> str | None:
    try:
        number = float(value)
    except (TypeError, ValueError):
        return None
    if number >= 1000:
        return f"${number / 1000:.1f}B"
    return f"${number:.1f}M"


def _timestamp_to_date(value: Any) -> str | None:
    try:
        timestamp = float(value) / 1000
    except (TypeError, ValueError):
        return None
    return datetime.fromtimestamp(timestamp, tz=timezone.utc).strftime("%Y-%m-%d")


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


def _strip_html(text: str) -> str:
    return re.sub(r"<[^>]+>", "", text or "").strip()


def _normalize_ascii(text: str) -> str:
    replacements = {
        "\u0105": "a",
        "\u0107": "c",
        "\u0119": "e",
        "\u0142": "l",
        "\u0144": "n",
        "\u00f3": "o",
        "\u015b": "s",
        "\u017c": "z",
        "\u017a": "z",
    }
    lowered = (text or "").lower()
    for source, target in replacements.items():
        lowered = lowered.replace(source, target)
    return re.sub(r"\s+", " ", lowered).strip()


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
