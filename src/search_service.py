from __future__ import annotations

import json
import re
import time
from dataclasses import dataclass
from datetime import datetime, timezone
from typing import Callable
from urllib.parse import urlparse

from src.config import Settings, load_settings
from src.logger import get_logger
from src.research_query_planner import plan_queries
from src.voice_commands import normalize_voice_command
from src.web_search import SearchResult, WebSearchBundle, search_brave, search_web


CURRENT_INFORMATION_HINTS = {
    "aktualnie",
    "aktualna",
    "aktualny",
    "teraz",
    "dzisiaj",
    "najnowsze",
    "najnowszy",
    "obecnie",
    "kto jest najbogatszy",
    "najbogatszy",
    "ranking",
    "kurs",
    "cena",
    "premiera",
    "prezydent",
    "premier",
    "ceo",
    "pogoda",
    "ostatnie informacje",
    "ostatnie wiadomosci",
    "wydarzenia",
    "wiadomosci",
    "kto jest teraz",
    "jaki jest obecny",
    "jaka jest obecna",
    "obecny ceo",
    "aktualny ceo",
    "wynik",
    "wyniki",
    "dzisiejszy",
    "dzisiejsza",
    "wartosc",
    "bitcoin",
    "akcje",
    "gielda",
}

CURRENT_INFORMATION_PATTERNS = (
    r"\b(kto|jaki|jaka|jakie)\s+jest\s+(teraz|obecnie|aktualnie|obecny|obecna|aktualny|aktualna)\b",
    r"\b(kto|jaki|jaka)\s+jest\s+.*\b(ceo|prezydent|premier|lider|szef)\b",
    r"\b(cena|kurs|wartosc|notowania|wynik|ranking)\b",
    r"\b(najnowsze|ostatnie)\s+(informacje|wiadomosci|wyniki|dane)\b",
    r"\b(co\s+sie\s+stalo|co\s+sie\s+dzieje)\b",
)

AUTHORITY_DOMAIN_HINTS = (
    "reuters.com",
    "apnews.com",
    "bbc.com",
    "forbes.com",
    "bloomberg.com",
    "gov",
    "edu",
    "wikipedia.org",
    "wikimedia.org",
    "open-meteo.com",
)

CURRENT_ANSWER_GUARDRAIL = (
    "To pytanie wymaga aktualnych danych. Nie korzystaj z wiedzy modelu jako "
    "zrodla prawdy. Odpowiedz tylko na podstawie zweryfikowanych zrodel ponizej. "
    "Nie mow, ze Twoja wiedza siega 2024. Jesli zrodla nie potwierdzaja odpowiedzi, "
    "powiedz: Nie mam wystarczajaco pewnych aktualnych danych."
)

CACHE_SCHEMA_VERSION = "current-search-v2"


@dataclass(frozen=True)
class SearchValidation:
    status: str
    confidence: float
    supported_claims: list[dict]
    contradictions: list[str]
    best_sources: list[dict]

    def as_dict(self) -> dict:
        return {
            "status": self.status,
            "confidence": self.confidence,
            "supported_claims": self.supported_claims,
            "contradictions": self.contradictions,
            "best_sources": self.best_sources,
        }


SearchProvider = Callable[[str, float, int], WebSearchBundle]

logger = get_logger(__name__)


def requires_current_information(text: str) -> bool:
    normalized = normalize_voice_command(text)
    if any(hint in normalized for hint in CURRENT_INFORMATION_HINTS):
        return True
    return any(re.search(pattern, normalized) for pattern in CURRENT_INFORMATION_PATTERNS)


def search_current_information(
    query: str,
    settings: Settings | None = None,
    provider: SearchProvider | None = None,
    limit: int | None = None,
) -> WebSearchBundle:
    active_settings = settings or load_settings()
    clean_query = " ".join((query or "").split()).strip()
    if not clean_query or not active_settings.web_search_enabled:
        return WebSearchBundle(query=clean_query, results=[], source="disabled")
    result_limit = limit or getattr(active_settings, "web_search_result_limit", 8)

    cached = _read_cached_bundle(clean_query, active_settings)
    if cached is not None:
        logger.info("Web search cache hit. query=%s results=%s", clean_query, len(cached.results))
        return cached

    search_fn = provider or _search_provider_from_settings(active_settings)
    logger.info(
        "Web search request. provider=%s query=%s",
        active_settings.web_search_provider,
        clean_query,
    )
    try:
        bundle = search_fn(clean_query, active_settings.web_search_timeout, result_limit)
    except Exception as error:
        logger.warning("Web search failed. query=%s error=%s", clean_query, error)
        return WebSearchBundle(query=clean_query, results=[], source="error")

    scored_bundle = WebSearchBundle(
        query=bundle.query,
        results=rank_search_results(clean_query, bundle.results)[:result_limit],
        source=bundle.source,
    )
    logger.info("Web search response. query=%s results=%s", clean_query, len(scored_bundle.results))
    _write_cached_bundle(clean_query, scored_bundle, active_settings)
    return scored_bundle


def search_current_information_for_question(
    question: str,
    settings: Settings | None = None,
    provider: SearchProvider | None = None,
    limit: int | None = None,
) -> WebSearchBundle:
    active_settings = settings or load_settings()
    plan = plan_queries(question, None)
    queries = plan.web_queries or [question]
    merged_results: list[SearchResult] = []
    sources = []
    result_limit = limit or getattr(active_settings, "web_search_result_limit", 8)
    for query in queries[:4]:
        bundle = search_current_information(
            query,
            settings=active_settings,
            provider=provider,
            limit=result_limit,
        )
        sources.append(bundle.source)
        merged_results.extend(bundle.results)
        if len(merged_results) >= result_limit and any(_is_authoritative_result(result) for result in merged_results):
            break
    ranked = rank_search_results(question, _dedupe_search_results(merged_results))[:result_limit]
    return WebSearchBundle(
        query=question,
        results=ranked,
        source="/".join(dict.fromkeys(source for source in sources if source)) or "web",
    )


def validate_search_results(question: str, answer: str, bundle: WebSearchBundle) -> SearchValidation:
    results = rank_search_results(question, bundle.results)[:4]
    if not results:
        return SearchValidation(
            status="unsupported",
            confidence=0.0,
            supported_claims=[],
            contradictions=["Brak wynikow wyszukiwania."],
            best_sources=[],
        )

    claims = []
    contradictions = []
    for result in results:
        text = result.snippet or result.title
        if not text:
            continue
        claims.append(
            {
                "text": text[:280],
                "source_url": result.url,
                "confidence": result.confidence,
            }
        )

    if _looks_conflicting(results):
        contradictions.append("Zrodla wygladaja na niespojne lub dotycza roznych tematow.")

    confidence = min(0.95, max(0.25, sum(result.confidence for result in results) / len(results)))
    if contradictions:
        confidence = min(confidence, 0.49)
    status = "supported" if claims and confidence >= 0.55 and not contradictions else "uncertain"
    return SearchValidation(
        status=status,
        confidence=round(confidence, 2),
        supported_claims=claims[:5],
        contradictions=contradictions if contradictions else ([] if status == "supported" else ["Zrodla sa zbyt slabe."]),
        best_sources=[result.as_dict() for result in results[:4]],
    )


def build_search_context(bundle: WebSearchBundle) -> str:
    if not bundle.results:
        return "\n".join(
            [
                CURRENT_ANSWER_GUARDRAIL,
                "Brak zweryfikowanych zrodel w aktualnym wyszukiwaniu.",
                "Odpowiedz: Nie mam wystarczajaco pewnych aktualnych danych.",
            ]
        )
    validation = validate_search_results(bundle.query, "", bundle)
    lines = [
        CURRENT_ANSWER_GUARDRAIL,
        (
            "Kontekst z aktualnego wyszukiwania w sieci, zweryfikowany przez JARVISA. "
            f"Status walidacji: {validation.status}, pewnosc: {validation.confidence}."
        ),
    ]
    for index, result in enumerate(rank_search_results(bundle.query, bundle.results)[:4], start=1):
        snippet = result.snippet or "brak opisu"
        published = f" | data: {result.published_at}" if result.published_at else ""
        lines.append(
            f"{index}. {result.title} | {result.url}{published} | "
            f"confidence={result.confidence:.2f} | {snippet}"
        )
    if validation.contradictions:
        lines.append(f"Ostrzezenia: {'; '.join(validation.contradictions)}")
    lines.append("Jesli te zrodla nie wystarczaja, powiedz wprost, ze nie masz wystarczajaco pewnych aktualnych danych.")
    return "\n".join(lines)


def rank_search_results(query: str, results: list[SearchResult]) -> list[SearchResult]:
    ranked = [
        SearchResult(
            title=result.title,
            url=result.url,
            snippet=result.snippet,
            image_url=result.image_url,
            source=result.source,
            published_at=result.published_at,
            confidence=score_search_result(query, result, results),
        )
        for result in results
    ]
    ranked.sort(key=lambda result: result.confidence, reverse=True)
    return ranked


def score_search_result(
    query: str,
    result: SearchResult,
    all_results: list[SearchResult] | None = None,
) -> float:
    evidence = f"{result.title} {result.snippet} {result.url} {result.source}"
    topic_score = _topic_match_score(query, evidence)
    freshness_score = _freshness_score(result.published_at)
    authority_score = _authority_score(result.url, result.source)
    source_type_score = 0.08 if result.snippet else 0.02
    cross_score = _cross_confirmation_score(result, all_results or [])
    heuristic = (
        topic_score * 0.34
        + freshness_score * 0.18
        + authority_score * 0.2
        + cross_score * 0.18
        + source_type_score
    )
    base = (result.confidence * 0.45) + (heuristic * 0.55)
    return round(max(0.05, min(0.98, base)), 2)


def _read_cached_bundle(query: str, settings: Settings) -> WebSearchBundle | None:
    if not settings.web_search_cache_enabled:
        return None
    cache_path = settings.web_search_cache_path
    try:
        data = json.loads(cache_path.read_text(encoding="utf-8"))
    except Exception:
        return None

    entry = data.get(_cache_key(query))
    if not entry:
        return None
    ttl_seconds = getattr(settings, "web_search_cache_ttl_seconds", 3600)
    if time.time() - float(entry.get("created_at", 0)) > ttl_seconds:
        return None
    return _bundle_from_dict(entry.get("bundle") or {})


def _write_cached_bundle(query: str, bundle: WebSearchBundle, settings: Settings) -> None:
    if not settings.web_search_cache_enabled:
        return
    cache_path = settings.web_search_cache_path
    cache_path.parent.mkdir(parents=True, exist_ok=True)
    try:
        data = json.loads(cache_path.read_text(encoding="utf-8"))
    except Exception:
        data = {}
    data[_cache_key(query)] = {
        "created_at": time.time(),
        "bundle": {
            "query": bundle.query,
            "source": bundle.source,
            "results": [result.as_dict() for result in bundle.results],
        },
    }
    cache_path.write_text(json.dumps(data, ensure_ascii=False, indent=2), encoding="utf-8")


def _bundle_from_dict(data: dict) -> WebSearchBundle:
    results = [
        SearchResult(
            title=str(item.get("title") or ""),
            url=str(item.get("url") or ""),
            snippet=str(item.get("snippet") or ""),
            image_url=item.get("image_url"),
            source=str(item.get("source") or "web"),
            published_at=item.get("published_at"),
            confidence=float(item.get("confidence", 0.65)),
        )
        for item in data.get("results", [])
        if item.get("title") and item.get("url")
    ]
    return WebSearchBundle(
        query=str(data.get("query") or ""),
        results=results,
        source=str(data.get("source") or "cache"),
    )


def _cache_key(query: str) -> str:
    return f"{CACHE_SCHEMA_VERSION}:{normalize_voice_command(query)}"


def _search_provider_from_settings(settings: Settings) -> SearchProvider:
    if settings.web_search_provider == "brave" and settings.web_search_api_key:
        return lambda query, timeout, limit: _combined_brave_search(query, settings, timeout, limit)
    return search_web


def _combined_brave_search(
    query: str,
    settings: Settings,
    timeout: float,
    limit: int,
) -> WebSearchBundle:
    fallback = search_web(query, timeout=timeout, limit=limit)
    brave = search_brave(
        query,
        settings.web_search_api_key or "",
        timeout=timeout,
        limit=limit,
    )
    return WebSearchBundle(
        query=query,
        results=_dedupe_search_results([*fallback.results, *brave.results])[:limit],
        source="Forbes/DuckDuckGo/Wikipedia/Brave",
    )


def _dedupe_search_results(results: list[SearchResult]) -> list[SearchResult]:
    unique = []
    seen = set()
    for result in results:
        key = (result.title.lower(), result.url.lower())
        if key in seen:
            continue
        seen.add(key)
        unique.append(result)
    return unique


def _is_authoritative_result(result: SearchResult) -> bool:
    evidence = f"{result.url} {result.source}".lower()
    return any(hint in evidence for hint in AUTHORITY_DOMAIN_HINTS)


def _topic_match_score(query: str, evidence: str) -> float:
    query_tokens = _important_tokens(query)
    evidence_normalized = normalize_voice_command(evidence)
    if not query_tokens:
        return 0.2
    matched = [token for token in query_tokens if token in evidence_normalized]
    first_phrase = " ".join(query_tokens[:2])
    phrase_bonus = 0.15 if first_phrase and first_phrase in evidence_normalized else 0.0
    return min(1.0, len(matched) / len(query_tokens) + phrase_bonus)


def _freshness_score(published_at: str | None) -> float:
    if not published_at:
        return 0.45
    parsed = _parse_date(published_at)
    if parsed is None:
        return 0.45
    age_days = max(0.0, (datetime.now(timezone.utc) - parsed).total_seconds() / 86400)
    if age_days <= 2:
        return 1.0
    if age_days <= 14:
        return 0.82
    if age_days <= 90:
        return 0.58
    return 0.28


def _authority_score(url: str, source: str) -> float:
    evidence = f"{url} {source}".lower()
    domain = urlparse(url).netloc.lower().removeprefix("www.")
    if any(hint in evidence or hint in domain for hint in AUTHORITY_DOMAIN_HINTS):
        return 1.0
    if domain:
        return 0.55
    return 0.25


def _cross_confirmation_score(result: SearchResult, results: list[SearchResult]) -> float:
    result_tokens = set(_important_tokens(f"{result.title} {result.snippet}"))
    if not result_tokens:
        return 0.25
    confirmations = 0
    for other in results:
        if other is result:
            continue
        other_tokens = set(_important_tokens(f"{other.title} {other.snippet}"))
        if len(result_tokens & other_tokens) >= 2:
            confirmations += 1
    if confirmations >= 2:
        return 1.0
    if confirmations == 1:
        return 0.72
    return 0.35


def _looks_conflicting(results: list[SearchResult]) -> bool:
    if len(results) < 2:
        return False
    title_tokens = [set(_important_tokens(result.title)) for result in results[:3]]
    if not title_tokens or not title_tokens[0]:
        return False
    return all(len(title_tokens[0] & tokens) == 0 for tokens in title_tokens[1:] if tokens)


def _important_tokens(text: str) -> list[str]:
    normalized = normalize_voice_command(text)
    stop_words = {
        "jest",
        "jaki",
        "jaka",
        "jakie",
        "kto",
        "co",
        "teraz",
        "obecnie",
        "aktualnie",
        "naj",
        "na",
        "w",
        "i",
        "oraz",
        "the",
        "and",
        "for",
    }
    return [
        token
        for token in re.findall(r"[a-z0-9]+", normalized)
        if len(token) > 2 and token not in stop_words
    ][:8]


def _parse_date(value: str) -> datetime | None:
    cleaned = (value or "").strip()
    if not cleaned:
        return None
    for pattern in ("%Y-%m-%d", "%Y-%m-%dT%H:%M:%S%z", "%Y-%m-%dT%H:%M:%SZ"):
        try:
            parsed = datetime.strptime(cleaned, pattern)
            if parsed.tzinfo is None:
                return parsed.replace(tzinfo=timezone.utc)
            return parsed.astimezone(timezone.utc)
        except ValueError:
            continue
    return None
