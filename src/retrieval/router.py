from __future__ import annotations

import re
import unicodedata

from src.retrieval.models import QueryPlan, SearchMode


REALTIME_HINTS = {
    "dzisiaj",
    "teraz",
    "aktualnie",
    "aktualny",
    "aktualna",
    "obecnie",
    "najnowsze",
    "najnowsza",
    "najnowszy",
    "najnowszego",
    "ostatnie",
    "ostatnio",
    "wczoraj",
    "jutro",
}

WEATHER_HINTS = {"pogoda", "temperatura", "deszcz", "wiatr", "zachmurzenie"}
FINANCE_HINTS = {"kurs", "cena", "bitcoin", "ethereum", "akcje", "gielda", "notowania", "wartosc"}
RANKING_HINTS = {"najbogatsz", "miliarder", "miliarderzy", "richest", "billionaire"}
NEWS_HINTS = {"news", "wiadomosci", "wiadomo", "wydarzylo", "wydarzenia", "co sie dzieje"}
SOFTWARE_HINTS = {"wersja", "release", "github", "pypi", "npm", "changelog", "fastapi"}
HIGH_RISK_HINTS = {
    "prezydent",
    "premier",
    "wybory",
    "ustawa",
    "prawo",
    "wojna",
    "atak",
    "sankcje",
    "zdrowie",
    "lek",
    "diagnoza",
}


class QueryRouter:
    def plan(self, question: str) -> QueryPlan:
        original = (question or "").strip()
        normalized = _normalize(original)
        if not normalized:
            return QueryPlan(
                original_question=original,
                needs_realtime=False,
                mode=SearchMode.NONE,
                reason="empty question",
            )

        mode = SearchMode.NONE
        reason = "stable knowledge question"
        needs_realtime = _contains_any(normalized, REALTIME_HINTS)
        min_sources = 1
        preferred_sources: list[str] = []

        if _contains_any(normalized, HIGH_RISK_HINTS):
            mode = SearchMode.HIGH_RISK
            needs_realtime = True
            reason = "high-risk/current affairs keywords"
            min_sources = 3
            preferred_sources = ["reuters.com", "apnews.com", "bbc.com", "gov.pl", "europa.eu"]
        elif _contains_any(normalized, NEWS_HINTS):
            mode = SearchMode.NEWS
            needs_realtime = True
            reason = "news keywords"
            preferred_sources = ["reuters.com", "apnews.com", "bbc.com"]
        elif _contains_any(normalized, FINANCE_HINTS) or _contains_any(normalized, RANKING_HINTS):
            mode = SearchMode.FINANCE
            needs_realtime = True
            reason = "finance/ranking keywords"
            preferred_sources = ["forbes.com", "bloomberg.com", "reuters.com"]
        elif _contains_any(normalized, SOFTWARE_HINTS):
            mode = SearchMode.SOFTWARE
            needs_realtime = True
            reason = "software release keywords"
            preferred_sources = ["github.com", "pypi.org", "npmjs.com", "fastapi.tiangolo.com"]
        elif _contains_any(normalized, WEATHER_HINTS):
            mode = SearchMode.WEB
            needs_realtime = True
            reason = "weather keywords; using web search when no weather API route is used"
            preferred_sources = ["weather.com", "metoffice.gov.uk", "open-meteo.com"]
        elif needs_realtime:
            mode = SearchMode.WEB
            reason = "realtime keywords"

        queries = _build_queries(original, normalized, mode, needs_realtime)
        required_domains, excluded_domains, min_trusted_sources, requires_official_source = _source_contract(
            normalized,
            mode,
            min_sources,
        )
        return QueryPlan(
            original_question=original,
            needs_realtime=needs_realtime,
            mode=mode if needs_realtime else SearchMode.NONE,
            search_queries=queries,
            preferred_sources=preferred_sources,
            required_domains=required_domains,
            excluded_domains=excluded_domains,
            reason=reason,
            min_sources=min_sources,
            min_trusted_sources=min_trusted_sources,
            requires_official_source=requires_official_source,
            freshness_required=needs_realtime,
        )


def _build_queries(original: str, normalized: str, mode: SearchMode, needs_realtime: bool) -> list[str]:
    if not needs_realtime:
        return []
    cleaned = re.sub(r"\s+", " ", original).strip(" ?!.,;:")
    queries = [cleaned]
    if mode == SearchMode.NEWS:
        queries.append(f"{cleaned} najnowsze wiadomosci")
    elif mode == SearchMode.FINANCE:
        if _contains_any(normalized, RANKING_HINTS):
            queries = [
                "Forbes real time billionaires richest person in the world",
                "Bloomberg billionaires index richest person in the world",
                f"{cleaned} Forbes Bloomberg Reuters",
            ]
        else:
            queries.append(f"{cleaned} aktualny kurs cena")
    elif mode == SearchMode.SOFTWARE:
        queries.append(f"{cleaned} latest release official")
    elif mode == SearchMode.HIGH_RISK:
        if _looks_like_us_president_query(normalized):
            queries = [
                "current president of the United States site:whitehouse.gov",
                "president of the United States site:usa.gov",
                "current US president Reuters AP",
                cleaned,
            ]
        else:
            queries.append(f"{cleaned} Reuters AP official")
    elif "najnowsz" not in normalized and "latest" not in normalized:
        queries.append(f"{cleaned} latest")
    return _dedupe(queries)


def _source_contract(
    normalized: str,
    mode: SearchMode,
    min_sources: int,
) -> tuple[list[str], list[str], int, bool]:
    excluded = [
        "facebook.com",
        "reddit.com",
        "youtube.com",
        "youtu.be",
        "tiktok.com",
        "instagram.com",
        "x.com",
        "twitter.com",
        "quora.com",
    ]
    required: list[str] = []
    min_trusted = min_sources
    requires_official = False
    if mode == SearchMode.HIGH_RISK and _looks_like_us_president_query(normalized):
        required = [
            "whitehouse.gov",
            "usa.gov",
            "congress.gov",
            "state.gov",
            "senate.gov",
            "house.gov",
        ]
        min_trusted = 2
        requires_official = True
    elif mode == SearchMode.FINANCE and _contains_any(normalized, RANKING_HINTS):
        min_trusted = 2
    return required, excluded, min_trusted, requires_official


def _contains_any(text: str, hints: set[str]) -> bool:
    return any(hint in text for hint in hints)


def _looks_like_us_president_query(normalized: str) -> bool:
    return (
        "prezydent" in normalized
        and any(term in normalized for term in ("stanow zjednoczonych", "usa", "us", "united states", "ameryki"))
    )


def _dedupe(items: list[str]) -> list[str]:
    seen = set()
    unique = []
    for item in items:
        key = _normalize(item)
        if not key or key in seen:
            continue
        seen.add(key)
        unique.append(item)
    return unique


def _normalize(text: str) -> str:
    lowered = unicodedata.normalize("NFKD", (text or "").lower())
    lowered = "".join(character for character in lowered if not unicodedata.combining(character))
    lowered = (
        lowered.replace("\u0142", "l")
        .replace("\u00f3", "o")
        .replace("\u015b", "s")
        .replace("\u017c", "z")
        .replace("\u017a", "z")
    )
    lowered = re.sub(r"[^a-z0-9 ]+", " ", lowered)
    return re.sub(r"\s+", " ", lowered).strip()
