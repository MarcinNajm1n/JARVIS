from __future__ import annotations

import json
import os
import re
import time
from datetime import datetime, timezone
from typing import Any
from zoneinfo import ZoneInfo

from src.config import Settings, load_settings
from src.retrieval.brave_provider import BraveProvider
from src.retrieval.evidence import EvidenceBuilder
from src.retrieval.fetcher import PageFetcher
from src.retrieval.models import (
    JarvisAnswer,
    OperationEvent,
    QueryPlan,
    RetrievalError,
    RetrievalResult,
    SearchMode,
    SearchResult,
)
from src.retrieval.router import QueryRouter
from src.retrieval.source_policy import (
    enrich_plan_with_source_policy,
    filter_search_results,
    is_quality_degraded,
    visual_asset_allowed,
    write_retrieval_trace,
)
from src.retrieval.tavily_provider import TavilyProvider


REALTIME_SYSTEM_PROMPT = """
Jestes Jarvis, asystent odpowiadajacy na podstawie aktualnie pobranych zrodel.
Jesli pytanie wymaga aktualnych danych, uzywaj wylacznie dostarczonego kontekstu.
Nie zgaduj.
Jesli zrodla sa sprzeczne, powiedz to jasno.
Podawaj date sprawdzenia.
Przy faktach podawaj zrodla.
Jesli nie masz wystarczajacych danych, odpowiedz: Nie mam wystarczajaco wiarygodnych danych.
Oddziel fakty od interpretacji.
Zwroc poprawny JSON zgodny ze schematem JarvisAnswer.
""".strip()


class RetrievalManager:
    def __init__(
        self,
        settings: Settings | None = None,
        router: QueryRouter | None = None,
        tavily_provider: TavilyProvider | None = None,
        brave_provider: BraveProvider | None = None,
        fetcher: PageFetcher | None = None,
        evidence_builder: EvidenceBuilder | None = None,
        cache: Any | None = None,
    ) -> None:
        self.settings = settings or load_settings()
        self.router = router or QueryRouter()
        self.tavily_provider = tavily_provider
        self.brave_provider = brave_provider
        self.fetcher = fetcher or PageFetcher(timeout_seconds=_setting(self.settings, "jarvis_fetch_timeout_seconds", 20.0))
        self.evidence_builder = evidence_builder or EvidenceBuilder(top_k=_setting(self.settings, "jarvis_rerank_top_k", 5))
        self.cache = cache if cache is not None else _build_cache(_setting(self.settings, "jarvis_cache_dir", None))

    def retrieve(self, question: str) -> RetrievalResult:
        checked_at = _checked_at(_setting(self.settings, "jarvis_timezone", "Europe/Warsaw"))
        operations = _OperationLog()
        operations.done("LISTENING", detail="question received")
        with operations.timed("CLASSIFYING"):
            plan = enrich_plan_with_source_policy(self.router.plan(question))

        if not plan.needs_realtime or not _setting(self.settings, "jarvis_enable_realtime_search", True):
            operations.done("SEARCH_SKIPPED", detail=plan.reason)
            return RetrievalResult(
                question=question,
                checked_at=checked_at,
                plan=plan,
                operations=operations.items,
            )

        errors: list[str] = []
        raw_search_results: list[SearchResult] = []
        search_results: list[SearchResult] = []
        rejected_results: list[dict[str, Any]] = []
        all_decisions = []
        provider_used = "none"
        used_fallback = False
        cached = self._read_cache(plan)
        if cached is not None:
            operations.done("SEARCH_CACHE_HIT", detail=f"{len(cached)} results")
            raw_search_results = cached
            provider_used = "cache"
            search_results, all_decisions = filter_search_results(raw_search_results, plan)
            rejected_results.extend(
                decision.as_dict() for decision in all_decisions if decision.status != "accepted"
            )
        else:
            try:
                with operations.timed("SEARCHING_TAVILY"):
                    raw_search_results = self._tavily().search(plan)
                    provider_used = "tavily"
            except RetrievalError as error:
                errors.append(str(error))
                operations.failed("SEARCHING_TAVILY", str(error))

            search_results, decisions = filter_search_results(raw_search_results, plan)
            all_decisions.extend(decisions)
            rejected_results.extend(
                decision.as_dict() for decision in decisions if decision.status != "accepted"
            )
            if (
                is_quality_degraded(raw_search_results, decisions, plan)
                and _setting(self.settings, "jarvis_enable_brave_fallback", True)
            ):
                used_fallback = True
                operations.done("PRIMARY SEARCH DEGRADED", detail="FALLBACK BRAVE ENGAGED")
                try:
                    with operations.timed("FALLBACK_BRAVE"):
                        brave_raw_results = self._brave().search(plan)
                        brave_results, brave_decisions = filter_search_results(brave_raw_results, plan)
                        all_decisions.extend(brave_decisions)
                        raw_search_results = [*raw_search_results, *brave_raw_results]
                        search_results = brave_results
                        provider_used = "brave"
                        rejected_results.extend(
                            decision.as_dict()
                            for decision in brave_decisions
                            if decision.status != "accepted"
                        )
                except RetrievalError as error:
                    errors.append(str(error))
                    operations.failed("FALLBACK_BRAVE", str(error))

            self._write_cache(plan, search_results)

        search_results = _dedupe_results(search_results)[: _setting(self.settings, "jarvis_search_max_results", 6)]
        write_retrieval_trace(
            _setting(self.settings, "retrieval_trace_path", None)
            or _setting(self.settings, "research_trace_path", None),
            question=question,
            plan=plan,
            provider=provider_used,
            raw_results=raw_search_results,
            decisions=all_decisions,
            used_fallback=used_fallback,
            errors=errors,
        )
        if not search_results:
            operations.failed("FETCHING_SOURCES", "no sources found")
            return RetrievalResult(
                question=question,
                checked_at=checked_at,
                plan=plan,
                search_results=[],
                operations=operations.items,
                used_fallback=used_fallback,
                errors=errors or ["no sources found"],
                rejected_results=rejected_results,
            )

        with operations.timed("FETCHING_SOURCES"):
            fetched_sources = self._fetch_sources(search_results, plan)

        with operations.timed("EXTRACTING_EVIDENCE"):
            evidence = self.evidence_builder.build(
                question,
                fetched_sources,
                top_k=_setting(self.settings, "jarvis_rerank_top_k", 5),
            )
        operations.done("RERANKING", detail=f"top {len(evidence)} chunks")

        visual_assets = [
            asset for asset in _visual_assets_from_results(search_results)
            if visual_asset_allowed(asset, plan)
        ]
        trusted_evidence_sources = {
            chunk.source_url
            for chunk in evidence
            if chunk.trust_score >= 0.62 and chunk.relevance_score >= 0.45
        }
        if plan.mode == SearchMode.HIGH_RISK.value and len(trusted_evidence_sources) < plan.min_trusted_sources:
            errors.append("high-risk question has fewer than required trusted sources")
            if _setting(self.settings, "strict_retrieval", True):
                evidence = []
                visual_assets = []

        return RetrievalResult(
            question=question,
            checked_at=checked_at,
            plan=plan,
            search_results=search_results,
            fetched_sources=fetched_sources,
            evidence=evidence,
            operations=operations.items,
            visual_assets=visual_assets,
            used_fallback=used_fallback,
            errors=errors,
            rejected_results=rejected_results,
        )

    def _tavily(self) -> TavilyProvider:
        if self.tavily_provider is not None:
            return self.tavily_provider
        return TavilyProvider(
            api_key=_setting(self.settings, "tavily_api_key", None),
            timeout_seconds=_setting(self.settings, "jarvis_search_timeout_seconds", 15.0),
            max_results=_setting(self.settings, "jarvis_search_max_results", 6),
        )

    def _brave(self) -> BraveProvider:
        if self.brave_provider is not None:
            return self.brave_provider
        return BraveProvider(
            api_key=_setting(self.settings, "brave_search_api_key", None)
            or _setting(self.settings, "web_search_api_key", None),
            timeout_seconds=_setting(self.settings, "jarvis_search_timeout_seconds", 15.0),
            max_results=_setting(self.settings, "jarvis_search_max_results", 6),
        )

    def _read_cache(self, plan: QueryPlan) -> list[SearchResult] | None:
        if self.cache is None or _should_bypass_cache(plan):
            return None
        key = _cache_key(plan)
        try:
            payload = self.cache.get(key)
        except Exception:
            return None
        if not payload:
            return None
        return [SearchResult.model_validate(item) for item in payload]

    def _write_cache(self, plan: QueryPlan, results: list[SearchResult]) -> None:
        if self.cache is None or _should_bypass_cache(plan) or not results:
            return
        try:
            self.cache.set(
                _cache_key(plan),
                [result.model_dump() for result in results],
                expire=_ttl_for_mode(plan.mode),
            )
        except Exception:
            return

    def _fetch_sources(self, results: list[SearchResult], plan: QueryPlan) -> list:
        fetched_sources = []
        to_fetch = []
        for result in results:
            cached = self._read_fetched_cache(result, plan)
            if cached is None:
                to_fetch.append(result)
            else:
                fetched_sources.append(cached)

        if to_fetch:
            fetched_sources.extend(self.fetcher.fetch_many(to_fetch, plan))
        for source in fetched_sources:
            self._write_fetched_cache(plan, source)
        return fetched_sources

    def _read_fetched_cache(self, result: SearchResult, plan: QueryPlan):
        if self.cache is None or _should_bypass_cache(plan):
            return None
        try:
            payload = self.cache.get(f"fetch-v1:{result.url}")
        except Exception:
            return None
        if not payload:
            return None
        from src.retrieval.models import FetchedSource

        return FetchedSource.model_validate(payload)

    def _write_fetched_cache(self, plan: QueryPlan, source) -> None:
        if self.cache is None or _should_bypass_cache(plan) or source.fetch_error:
            return
        try:
            self.cache.set(
                f"fetch-v1:{source.url}",
                source.model_dump(),
                expire=_ttl_for_mode(plan.mode),
            )
        except Exception:
            return


def build_realtime_llm_prompt(question: str, result: RetrievalResult) -> str:
    schema = {
        "answer": "pelna odpowiedz na ekran",
        "spoken_answer": "krotka odpowiedz do TTS bez URL",
        "confidence": "high|medium|low",
        "display_type": "jarvis_tactical_hud",
        "checked_at": result.checked_at,
        "sources": [
            {
                "title": "tytul",
                "url": "https://...",
                "summary": "krotki opis",
                "provider": "tavily/brave",
                "trust_score": 0.9,
                "relevance_score": 0.87,
            }
        ],
        "operations": [{"name": "SEARCHING_TAVILY", "status": "done", "duration_ms": 120}],
        "visual_assets": [{"type": "image", "url": "https://...", "caption": "opis"}],
    }
    return "\n\n".join(
        [
            REALTIME_SYSTEM_PROMPT,
            f"Pytanie uzytkownika:\n{question}",
            f"Data sprawdzenia:\n{result.checked_at}",
            f"Zrodla:\n{result.context_for_llm()}",
            "Operacje systemowe:\n"
            + json.dumps([operation.model_dump() for operation in result.operations], ensure_ascii=False),
            "Zrodla do payloadu:\n" + json.dumps(result.source_payloads(), ensure_ascii=False),
            "Visual assets:\n" + json.dumps(result.visual_assets, ensure_ascii=False),
            "Schemat JSON:\n" + json.dumps(schema, ensure_ascii=False),
            "Zwroc wylacznie JSON. Bez markdown.",
        ]
    )


def parse_jarvis_answer(raw_text: str, result: RetrievalResult) -> JarvisAnswer:
    try:
        data = _extract_json(raw_text)
        answer = JarvisAnswer.model_validate(data)
    except Exception:
        return result.fallback_answer()

    if _contains_url(answer.spoken_answer):
        answer = answer.model_copy(update={"spoken_answer": _remove_urls(answer.spoken_answer)})
    if not answer.sources:
        answer = answer.model_copy(update={"sources": result.source_payloads()})
    if not answer.operations:
        answer = answer.model_copy(update={"operations": [operation.model_dump() for operation in result.operations]})
    if not answer.visual_assets:
        answer = answer.model_copy(update={"visual_assets": result.visual_assets})
    return answer


class _OperationLog:
    def __init__(self) -> None:
        self.items: list[OperationEvent] = []

    def done(self, name: str, duration_ms: int = 0, detail: str | None = None) -> None:
        self.items.append(OperationEvent(name=name, status="done", duration_ms=duration_ms, detail=detail))

    def failed(self, name: str, detail: str) -> None:
        self.items.append(OperationEvent(name=name, status="failed", duration_ms=0, detail=detail))

    def timed(self, name: str) -> "_TimedOperation":
        return _TimedOperation(self, name)


class _TimedOperation:
    def __init__(self, log: _OperationLog, name: str) -> None:
        self.log = log
        self.name = name
        self.started = 0.0

    def __enter__(self) -> None:
        self.started = time.perf_counter()

    def __exit__(self, exc_type, exc, tb) -> None:
        if exc_type is not None:
            return
        duration_ms = int((time.perf_counter() - self.started) * 1000)
        self.log.done(self.name, duration_ms=duration_ms)


def _checked_at(timezone_name: str) -> str:
    try:
        tz = ZoneInfo(timezone_name)
    except Exception:
        tz = timezone.utc
    return datetime.now(tz).isoformat(timespec="seconds")


def _setting(settings: Any, name: str, default: Any) -> Any:
    return getattr(settings, name, default)


def _build_cache(cache_dir: str | os.PathLike | None) -> Any | None:
    if not cache_dir:
        return None
    try:
        from diskcache import Cache

        return Cache(str(cache_dir))
    except Exception:
        return None


def _should_bypass_cache(plan: QueryPlan) -> bool:
    normalized = plan.original_question.lower()
    return plan.mode == SearchMode.HIGH_RISK.value or any(
        hint in normalized
        for hint in ("teraz", "dzisiaj", "aktualnie", "obecnie", "najnowsz", "kto jest")
    )


def _ttl_for_mode(mode: str) -> int:
    return {
        SearchMode.NEWS.value: 600,
        SearchMode.FINANCE.value: 60,
        SearchMode.SOFTWARE.value: 21_600,
        SearchMode.HIGH_RISK.value: 900,
    }.get(mode, 86_400)


def _cache_key(plan: QueryPlan) -> str:
    query = "|".join(plan.search_queries)
    return f"retrieval-v1:{plan.mode}:{query}"


def _dedupe_results(results: list[SearchResult]) -> list[SearchResult]:
    seen = set()
    unique = []
    for result in results:
        key = result.url.lower()
        if key in seen:
            continue
        seen.add(key)
        unique.append(result)
    return unique


def _visual_assets_from_results(results: list[SearchResult]) -> list[dict[str, Any]]:
    assets = []
    seen = set()
    for result in results:
        if not result.image_url or result.image_url in seen:
            continue
        seen.add(result.image_url)
        assets.append(
            {
                "type": "image",
                "url": result.image_url,
                "caption": result.title,
                "source_url": result.url,
            }
        )
        if len(assets) >= 4:
            break
    return assets


def _extract_json(raw_text: str) -> dict[str, Any]:
    cleaned = (raw_text or "").strip()
    if cleaned.startswith("```"):
        cleaned = re.sub(r"^```(?:json)?", "", cleaned).strip()
        cleaned = re.sub(r"```$", "", cleaned).strip()
    try:
        return json.loads(cleaned)
    except json.JSONDecodeError:
        match = re.search(r"\{.*\}", cleaned, flags=re.DOTALL)
        if not match:
            raise
        return json.loads(match.group(0))


def _contains_url(text: str) -> bool:
    return bool(re.search(r"https?://|www\.", text or ""))


def _remove_urls(text: str) -> str:
    cleaned = re.sub(r"https?://\S+|www\.\S+", "", text or "")
    return re.sub(r"\s+", " ", cleaned).strip()
