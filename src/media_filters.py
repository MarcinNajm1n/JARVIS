from __future__ import annotations

import re
import unicodedata
from urllib.parse import urlparse

from src.research_models import ImageResult, ReportResult, ResearchFilters, VideoResult
from src.web_search import SearchResult


TRUSTED_IMAGE_DOMAINS = (
    "wikimedia.org",
    "wikipedia.org",
    "commons.wikimedia.org",
    "staticflickr.com",
    "nasa.gov",
    "gov",
    "edu",
)

VIDEO_DOMAINS = ("youtube.com", "youtu.be", "vimeo.com", "ted.com")
REPORT_HINTS = ("pdf", "report", "raport", "research", "study", "badanie", "whitepaper")
VIDEO_HINTS = ("video", "film", "documentary", "interview", "youtube", "wywiad")
PLACEHOLDER_HINTS = ("placeholder", "sprite", "icon", "logo", "avatar-default")


def filter_images(
    candidates: list[ImageResult],
    filters: ResearchFilters,
    limit: int = 4,
) -> list[ImageResult]:
    ranked = []
    seen = set()
    for candidate in candidates:
        key = candidate.image_url.lower()
        if key in seen:
            continue
        seen.add(key)
        score, reasons = score_image(candidate, filters)
        if score <= 0:
            continue
        ranked.append(
            ImageResult(
                image_url=candidate.image_url,
                thumbnail_url=candidate.thumbnail_url,
                page_url=candidate.page_url,
                caption=candidate.caption,
                source=candidate.source,
                width=candidate.width,
                height=candidate.height,
                license=candidate.license,
                confidence=round(min(0.98, score), 2),
                validation={"status": "accepted", "reasons": reasons},
            )
        )
    ranked.sort(key=lambda item: item.confidence, reverse=True)
    return ranked[:limit]


def filter_reports(
    candidates: list[ReportResult],
    filters: ResearchFilters,
    limit: int = 4,
) -> list[ReportResult]:
    ranked = []
    seen = set()
    for candidate in candidates:
        key = candidate.url.lower()
        if key in seen:
            continue
        seen.add(key)
        score, reasons = score_report(candidate, filters)
        if score <= 0:
            continue
        ranked.append(
            ReportResult(
                title=candidate.title,
                url=candidate.url,
                file_type=candidate.file_type,
                publisher=candidate.publisher,
                published_at=candidate.published_at,
                snippet=candidate.snippet,
                confidence=round(min(0.98, score), 2),
                validation={"status": "accepted", "reasons": reasons},
            )
        )
    ranked.sort(key=lambda item: item.confidence, reverse=True)
    return ranked[:limit]


def filter_videos(
    candidates: list[VideoResult],
    filters: ResearchFilters,
    limit: int = 4,
) -> list[VideoResult]:
    ranked = []
    seen = set()
    for candidate in candidates:
        key = candidate.url.lower()
        if key in seen:
            continue
        seen.add(key)
        score, reasons = score_video(candidate, filters)
        if score <= 0:
            continue
        ranked.append(
            VideoResult(
                title=candidate.title,
                url=candidate.url,
                thumbnail_url=candidate.thumbnail_url,
                duration=candidate.duration,
                channel=candidate.channel,
                published_at=candidate.published_at,
                source=candidate.source,
                confidence=round(min(0.98, score), 2),
                validation={"status": "accepted", "reasons": reasons},
            )
        )
    ranked.sort(key=lambda item: item.confidence, reverse=True)
    return ranked[:limit]


def score_image(candidate: ImageResult, filters: ResearchFilters) -> tuple[float, list[str]]:
    if not candidate.image_url:
        return 0.0, ["missing_image_url"]
    if _has_placeholder(candidate.image_url):
        return 0.0, ["placeholder_image"]

    evidence = " ".join(
        [
            candidate.caption,
            candidate.page_url or "",
            candidate.source,
            candidate.image_url,
        ]
    )
    score, reasons = _base_topic_score(evidence, filters)
    if score <= 0:
        return 0.0, ["topic_mismatch"]

    domain = _domain(candidate.page_url or candidate.image_url)
    if _domain_matches(domain, TRUSTED_IMAGE_DOMAINS):
        score += 0.18
        reasons.append("trusted_image_domain")
    if candidate.width and candidate.height and candidate.width >= 420 and candidate.height >= 280:
        score += 0.08
        reasons.append("usable_dimensions")
    return min(score, 0.98), reasons


def score_report(candidate: ReportResult, filters: ResearchFilters) -> tuple[float, list[str]]:
    evidence = f"{candidate.title} {candidate.snippet} {candidate.url} {candidate.publisher or ''}"
    score, reasons = _base_topic_score(evidence, filters)
    if score <= 0:
        return 0.0, ["topic_mismatch"]

    normalized = _normalize(evidence)
    if any(hint in normalized for hint in REPORT_HINTS) or candidate.file_type == "pdf":
        score += 0.18
        reasons.append("report_hint")
    domain = _domain(candidate.url)
    if domain.endswith(".gov") or domain.endswith(".edu") or "gov" in domain or "edu" in domain:
        score += 0.12
        reasons.append("institutional_domain")
    return min(score, 0.98), reasons


def score_video(candidate: VideoResult, filters: ResearchFilters) -> tuple[float, list[str]]:
    evidence = f"{candidate.title} {candidate.url} {candidate.channel or ''} {candidate.source}"
    score, reasons = _base_topic_score(evidence, filters)
    if score <= 0:
        return 0.0, ["topic_mismatch"]

    normalized = _normalize(evidence)
    if any(hint in normalized for hint in VIDEO_HINTS):
        score += 0.12
        reasons.append("video_hint")
    if _domain_matches(_domain(candidate.url), VIDEO_DOMAINS):
        score += 0.18
        reasons.append("video_domain")
    return min(score, 0.98), reasons


def image_candidates_from_search_results(results: list[SearchResult]) -> list[ImageResult]:
    candidates = []
    for result in results:
        if not result.image_url:
            continue
        candidates.append(
            ImageResult(
                image_url=result.image_url,
                thumbnail_url=result.image_url,
                page_url=result.url,
                caption=result.title or result.snippet,
                source=result.source,
                confidence=result.confidence,
            )
        )
    return candidates


def report_candidates_from_search_results(results: list[SearchResult]) -> list[ReportResult]:
    candidates = []
    for result in results:
        evidence = _normalize(f"{result.title} {result.snippet} {result.url}")
        if not any(hint in evidence for hint in REPORT_HINTS):
            continue
        file_type = "pdf" if ".pdf" in result.url.lower() or "pdf" in evidence else "web"
        candidates.append(
            ReportResult(
                title=result.title,
                url=result.url,
                file_type=file_type,
                publisher=result.source,
                published_at=result.published_at,
                snippet=result.snippet,
                confidence=result.confidence,
            )
        )
    return candidates


def video_candidates_from_search_results(results: list[SearchResult]) -> list[VideoResult]:
    candidates = []
    for result in results:
        evidence = _normalize(f"{result.title} {result.snippet} {result.url}")
        if not any(hint in evidence for hint in VIDEO_HINTS) and not _domain_matches(
            _domain(result.url),
            VIDEO_DOMAINS,
        ):
            continue
        candidates.append(
            VideoResult(
                title=result.title,
                url=result.url,
                thumbnail_url=result.image_url,
                channel=result.source,
                published_at=result.published_at,
                source=result.source,
                confidence=result.confidence,
            )
        )
    return candidates


def _base_topic_score(evidence: str, filters: ResearchFilters) -> tuple[float, list[str]]:
    normalized = _normalize(evidence)
    reasons = []
    if not normalized:
        return 0.0, ["empty_evidence"]

    for forbidden in filters.must_not_include:
        if _normalize(forbidden) in normalized:
            return 0.0, ["excluded_term"]

    aliases = [_normalize(alias) for alias in [*filters.entity_aliases, *filters.must_include]]
    aliases = [alias for alias in aliases if alias]
    matched_aliases = [alias for alias in aliases if _matches_alias(alias, normalized)]
    if not matched_aliases:
        return 0.0, ["missing_required_topic"]

    score = 0.46 + min(0.28, len(matched_aliases) * 0.08)
    reasons.append("topic_match")
    if any(_domain_matches(_domain(evidence), [domain]) for domain in filters.preferred_domains):
        score += 0.08
        reasons.append("preferred_domain")
    return score, reasons


def _matches_alias(alias: str, text: str) -> bool:
    if alias in text:
        return True
    tokens = [token for token in alias.split() if len(token) > 2]
    return bool(tokens) and all(token in text for token in tokens)


def _domain(value: str) -> str:
    parsed = urlparse(value if "://" in value else f"https://{value}")
    return parsed.netloc.lower().removeprefix("www.")


def _domain_matches(domain: str, allowed: tuple[str, ...] | list[str]) -> bool:
    return any(item in domain for item in allowed if item)


def _has_placeholder(value: str) -> bool:
    normalized = _normalize(value)
    return any(hint in normalized for hint in PLACEHOLDER_HINTS)


def _normalize(text: str) -> str:
    lowered = unicodedata.normalize("NFKD", (text or "").lower())
    lowered = "".join(character for character in lowered if not unicodedata.combining(character))
    lowered = (
        lowered.replace("\u0142", "l")
        .replace("\u0141", "l")
        .replace("\u00f3", "o")
    )
    lowered = re.sub(r"[^a-z0-9 .:/_-]+", " ", lowered)
    return re.sub(r"\s+", " ", lowered).strip()
