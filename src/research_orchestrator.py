from __future__ import annotations

import json
import re
import time
from typing import Callable

from src.config import Settings, load_settings
from src.image_display import prepare_display_images
from src.llm_validator import validate_research_brief
from src.logger import get_logger
from src.media_filters import (
    filter_images,
    filter_reports,
    filter_videos,
    image_candidates_from_search_results,
    report_candidates_from_search_results,
    video_candidates_from_search_results,
)
from src.research_models import (
    ImageResult,
    ValidatedEvidence,
    VisualBrief,
)
from src.research_query_planner import plan_queries
from src.search_service import search_current_information, validate_search_results
from src.web_search import WebSearchBundle


SearchProvider = Callable[[str, float, int], WebSearchBundle]

logger = get_logger(__name__)


def build_research_brief(
    question: str,
    answer: str,
    search_bundle: WebSearchBundle | None = None,
    settings: Settings | None = None,
    search_provider: SearchProvider | None = None,
) -> dict | None:
    active_settings = settings or load_settings()
    plan = plan_queries(question, answer)
    trace = {
        "question": _compact(question, 220),
        "answer_excerpt": _compact(answer, 320),
        "topic": plan.topic,
        "intent": plan.intent,
        "queries": plan.as_dict()["queries"],
        "selected_query": None,
        "source": "research_orchestrator",
        "validation_steps": [],
    }

    if not plan.topic or plan.topic == "Temat":
        trace["validation_steps"].append("no_topic")
        _append_trace(active_settings, trace)
        return None

    bundle = _ensure_topic_bundle(plan.topic, search_bundle, active_settings, search_provider)
    trace["selected_query"] = bundle.query or plan.topic
    trace["result_count"] = len(bundle.results)
    if not bundle.results:
        trace["validation_steps"].append("no_search_results")
        _append_trace(active_settings, trace)
        return None

    filtered_bundle = WebSearchBundle(
        query=bundle.query,
        results=[
            result
            for result in bundle.results
            if _topic_in_text(plan.topic, f"{result.title} {result.snippet} {result.url}")
        ],
        source=bundle.source,
    )
    if not filtered_bundle.results:
        trace["validation_steps"].append("all_results_rejected_topic_mismatch")
        _append_trace(active_settings, trace)
        return None

    validation = validate_search_results(plan.topic, answer, filtered_bundle).as_dict()
    evidence = _evidence_from_bundle(filtered_bundle)
    images = prepare_display_images(_collect_images(filtered_bundle, plan.filters), plan.topic)
    reports = filter_reports(report_candidates_from_search_results(filtered_bundle.results), plan.filters)
    videos = filter_videos(video_candidates_from_search_results(filtered_bundle.results), plan.filters)
    summary = _summary_from_answer_or_sources(answer, filtered_bundle)
    sources = _sources_from_bundle(filtered_bundle)

    brief = VisualBrief(
        topic=plan.topic,
        title=plan.topic,
        summary=summary,
        confidence=validation.get("confidence", 0.0),
        images=images,
        videos=videos,
        reports=reports,
        evidence=evidence,
        sources=sources,
        validation=validation,
        trace=trace,
    )

    validator_result = validate_research_brief(question, answer, brief, active_settings)
    min_confidence = getattr(active_settings, "llm_validator_min_confidence", 0.72)
    if (
        validator_result["status"] == "rejected"
        or (images and validator_result["confidence"] < min_confidence and validation["confidence"] < 0.5)
    ):
        trace["validation_steps"].append("validator_rejected_display")
        brief = VisualBrief(
            topic=plan.topic,
            title="Brak pewnego displaya",
            summary="Nie pokazuje displaya, bo media lub zrodla nie pokrywaja sie pewnie z odpowiedzia.",
            confidence=validator_result["confidence"],
            images=[],
            videos=[],
            reports=[],
            evidence=[],
            sources=sources,
            validation={**validator_result, "status": "rejected"},
            trace=trace,
        )
    else:
        brief = VisualBrief(
            topic=brief.topic,
            title=brief.title,
            summary=brief.summary,
            confidence=max(float(brief.confidence), float(validator_result["confidence"])),
            images=brief.images,
            videos=brief.videos,
            reports=brief.reports,
            evidence=brief.evidence,
            sources=brief.sources,
            validation={**validation, "display_validator": validator_result},
            trace=trace,
        )

    trace["validation_steps"].append("research_brief_ready")
    trace["image_count"] = len(brief.images)
    trace["report_count"] = len(brief.reports)
    trace["video_count"] = len(brief.videos)
    trace["confidence"] = brief.confidence
    _append_trace(active_settings, trace)
    payload = brief.as_visual_payload()
    payload["research_plan"] = plan.as_dict()
    return payload


def _ensure_topic_bundle(
    topic: str,
    search_bundle: WebSearchBundle | None,
    settings: Settings,
    search_provider: SearchProvider | None,
) -> WebSearchBundle:
    if search_bundle and _topic_in_text(topic, search_bundle.query):
        return search_bundle
    if search_bundle and any(
        _topic_in_text(topic, f"{result.title} {result.snippet} {result.url}")
        for result in search_bundle.results
    ):
        return search_bundle
    if search_provider is not None:
        try:
            return search_provider(topic, settings.web_search_timeout, 8)
        except Exception as error:
            logger.warning("Research provider failed. topic=%s error=%s", topic, error)
            return WebSearchBundle(query=topic, results=[], source="error")
    return search_current_information(topic, settings=settings, provider=search_provider, limit=8)


def _collect_images(bundle: WebSearchBundle, filters) -> list[ImageResult]:
    candidates = image_candidates_from_search_results(bundle.results)
    if not candidates and bundle.best and _topic_in_text(filters.must_include[0], bundle.best.title):
        # Keep the display useful even when the search provider has only page
        # metadata. The UI will show text/sources, not a fake image.
        candidates = []
    return filter_images(candidates, filters)


def _evidence_from_bundle(bundle: WebSearchBundle) -> list[ValidatedEvidence]:
    evidence = []
    for result in bundle.results[:5]:
        claim = result.snippet or result.title
        if not claim:
            continue
        evidence.append(
            ValidatedEvidence(
                claim=_compact(claim, 220),
                source_url=result.url,
                source_title=result.title,
                confidence=result.confidence,
            )
        )
    return evidence


def _sources_from_bundle(bundle: WebSearchBundle) -> list[str]:
    sources = []
    seen = set()
    for result in bundle.results[:6]:
        if not result.url or result.url in seen:
            continue
        seen.add(result.url)
        sources.append(result.url)
    return sources


def _summary_from_answer_or_sources(answer: str, bundle: WebSearchBundle) -> str:
    answer_summary = _compact(answer, 420)
    if answer_summary:
        return answer_summary
    if bundle.best:
        return _compact(bundle.best.snippet or bundle.best.title, 420)
    return "Brak pewnego opisu."


def _topic_in_text(topic: str, text: str) -> bool:
    normalized_topic = _normalize(topic)
    normalized_text = _normalize(text)
    if not normalized_topic or not normalized_text:
        return False
    if normalized_topic in normalized_text:
        return True
    tokens = [token for token in normalized_topic.split() if len(token) > 2]
    return bool(tokens) and all(token in normalized_text for token in tokens)


def _normalize(text: str) -> str:
    lowered = (text or "").lower()
    lowered = (
        lowered.replace("\u0105", "a")
        .replace("\u0107", "c")
        .replace("\u0119", "e")
        .replace("\u0142", "l")
        .replace("\u0144", "n")
        .replace("\u00f3", "o")
        .replace("\u015b", "s")
        .replace("\u017c", "z")
        .replace("\u017a", "z")
    )
    lowered = re.sub(r"[^a-z0-9 ]+", " ", lowered)
    return re.sub(r"\s+", " ", lowered).strip()


def _compact(text: str, limit: int) -> str:
    cleaned = re.sub(r"\s+", " ", text or "").strip()
    if len(cleaned) <= limit:
        return cleaned
    return cleaned[: max(0, limit - 1)].rstrip() + "..."


def _append_trace(settings: Settings, trace: dict) -> None:
    trace_path = getattr(settings, "research_trace_path", None)
    if trace_path is None:
        return
    enriched = {"created_at": time.time(), **trace}
    try:
        trace_path.parent.mkdir(parents=True, exist_ok=True)
        data = json.loads(trace_path.read_text(encoding="utf-8"))
    except Exception:
        data = []
    if not isinstance(data, list):
        data = []
    data.append(enriched)
    del data[:-80]
    try:
        trace_path.write_text(json.dumps(data, ensure_ascii=False, indent=2), encoding="utf-8")
    except Exception as error:
        logger.warning("Could not write research trace: %s", error)
