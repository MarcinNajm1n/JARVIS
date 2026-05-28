from __future__ import annotations

import json
import re
from dataclasses import asdict, dataclass
from datetime import datetime, timezone
from pathlib import Path
from urllib.parse import urlparse

from src.retrieval.evidence import score_source
from src.retrieval.models import QueryPlan, SearchMode, SearchResult


SOCIAL_BLOCKED_DOMAINS = (
    "facebook.com",
    "m.facebook.com",
    "reddit.com",
    "youtube.com",
    "youtu.be",
    "tiktok.com",
    "instagram.com",
    "x.com",
    "twitter.com",
    "quora.com",
    "pinterest.com",
    "threads.net",
)

SEO_BLOCKED_HINTS = (
    "coupon",
    "casino",
    "clickbait",
    "promo-code",
    "affiliate",
    "best-",
    "top10",
    "ranker.com",
)

US_OFFICIAL_DOMAINS = (
    "whitehouse.gov",
    "usa.gov",
    "congress.gov",
    "state.gov",
    "senate.gov",
    "house.gov",
    "federalregister.gov",
    "archives.gov",
)

OFFICIAL_DOMAINS = (
    *US_OFFICIAL_DOMAINS,
    "gov.pl",
    "europa.eu",
    "ec.europa.eu",
    "who.int",
    "un.org",
    "nato.int",
)

WIRE_DOMAINS = ("reuters.com", "apnews.com", "bbc.com", "bloomberg.com", "ft.com")
RANKING_DOMAINS = ("forbes.com", "bloomberg.com", "reuters.com")
SOFTWARE_DOMAINS = ("github.com", "pypi.org", "npmjs.com", "fastapi.tiangolo.com")


@dataclass(frozen=True)
class SourceDecision:
    url: str
    title: str
    domain: str
    status: str
    reason: str
    trust_score: float
    provider: str

    def as_dict(self) -> dict[str, object]:
        return asdict(self)


def enrich_plan_with_source_policy(plan: QueryPlan) -> QueryPlan:
    required = list(plan.required_domains)
    preferred = list(plan.preferred_sources)
    excluded = _dedupe([*plan.excluded_domains, *SOCIAL_BLOCKED_DOMAINS])
    requires_official = plan.requires_official_source
    min_trusted = plan.min_trusted_sources or 1
    freshness_required = plan.freshness_required or plan.needs_realtime

    normalized = _normalize(plan.original_question)
    mode = str(plan.mode)
    if mode == SearchMode.HIGH_RISK.value:
        preferred = _dedupe([*preferred, *WIRE_DOMAINS, *OFFICIAL_DOMAINS])
        min_trusted = max(min_trusted, plan.min_sources, 3)
        if _looks_like_us_president_query(normalized):
            required = _dedupe([*required, *US_OFFICIAL_DOMAINS])
            requires_official = True
            min_trusted = min(min_trusted, 2)
    elif mode == SearchMode.FINANCE.value and _looks_like_richest_query(normalized):
        preferred = _dedupe([*RANKING_DOMAINS, *preferred])
        min_trusted = max(min_trusted, 2)
    elif mode == SearchMode.SOFTWARE.value:
        preferred = _dedupe([*SOFTWARE_DOMAINS, *preferred])

    return plan.model_copy(
        update={
            "preferred_sources": _dedupe(preferred),
            "required_domains": _dedupe(required),
            "excluded_domains": excluded,
            "min_trusted_sources": min_trusted,
            "requires_official_source": requires_official,
            "freshness_required": freshness_required,
        }
    )


def filter_search_results(
    results: list[SearchResult],
    plan: QueryPlan,
) -> tuple[list[SearchResult], list[SourceDecision]]:
    accepted: list[SearchResult] = []
    decisions: list[SourceDecision] = []
    for result in results:
        decision = evaluate_search_result(result, plan)
        decisions.append(decision)
        if decision.status == "accepted":
            accepted.append(result)
    return accepted, decisions


def evaluate_search_result(result: SearchResult, plan: QueryPlan) -> SourceDecision:
    domain = domain_from_url(result.url)
    trust_score = score_source(result.url, plan.mode, plan.original_question)
    evidence = f"{domain} {result.url} {result.title} {result.snippet or ''}".lower()
    mode = str(plan.mode)

    if _domain_matches(domain, plan.excluded_domains) or _domain_matches(domain, SOCIAL_BLOCKED_DOMAINS):
        return _decision(result, domain, "rejected_social", "blocked social/UGC domain", trust_score)
    if any(hint in evidence for hint in SEO_BLOCKED_HINTS):
        return _decision(result, domain, "rejected_low_trust", "blocked SEO/spam hint", trust_score)

    if mode == SearchMode.HIGH_RISK.value:
        if plan.required_domains and _domain_matches(domain, plan.required_domains):
            return _decision(result, domain, "accepted", "required official domain", max(trust_score, 0.9))
        if _domain_matches(domain, plan.preferred_sources) or _domain_matches(domain, WIRE_DOMAINS):
            return _decision(result, domain, "accepted", "trusted high-risk source", max(trust_score, 0.75))
        if trust_score < 0.62:
            return _decision(result, domain, "rejected_low_trust", "high-risk source below trust threshold", trust_score)

    if mode == SearchMode.FINANCE.value and _looks_like_richest_query(_normalize(plan.original_question)):
        if _domain_matches(domain, RANKING_DOMAINS):
            return _decision(result, domain, "accepted", "trusted ranking source", max(trust_score, 0.82))
        return _decision(result, domain, "rejected_wrong_domain", "ranking query requires Forbes/Bloomberg/Reuters", trust_score)

    if plan.preferred_sources and _domain_matches(domain, plan.preferred_sources):
        return _decision(result, domain, "accepted", "preferred domain", max(trust_score, 0.75))
    if trust_score < 0.25:
        return _decision(result, domain, "rejected_low_trust", "source below trust threshold", trust_score)
    return _decision(result, domain, "accepted", "general trusted enough", trust_score)


def is_quality_degraded(results: list[SearchResult], decisions: list[SourceDecision], plan: QueryPlan) -> bool:
    if not results:
        return True
    accepted = [decision for decision in decisions if decision.status == "accepted"]
    trusted = [decision for decision in accepted if decision.trust_score >= 0.62]
    if not accepted:
        return True
    if str(plan.mode) == SearchMode.HIGH_RISK.value:
        if plan.requires_official_source and not any(
            _domain_matches(decision.domain, plan.required_domains) for decision in accepted
        ):
            return True
        return len(trusted) < min(plan.min_trusted_sources, 3)
    return False


def visual_asset_allowed(asset: dict[str, object], plan: QueryPlan) -> bool:
    source_url = str(asset.get("source_url") or asset.get("url") or "")
    caption = str(asset.get("caption") or "")
    domain = domain_from_url(source_url)
    if _domain_matches(domain, plan.excluded_domains) or _domain_matches(domain, SOCIAL_BLOCKED_DOMAINS):
        return False
    if str(plan.mode) == SearchMode.HIGH_RISK.value and not (
        _domain_matches(domain, plan.required_domains)
        or _domain_matches(domain, plan.preferred_sources)
        or _domain_matches(domain, WIRE_DOMAINS)
    ):
        return False
    normalized_question = _normalize(plan.original_question)
    normalized_caption = _normalize(caption)
    if _looks_like_richest_query(normalized_question):
        return _domain_matches(domain, RANKING_DOMAINS) and _shares_topic_tokens(
            normalized_question,
            normalized_caption,
        )
    return True


def write_retrieval_trace(
    trace_path: Path | None,
    *,
    question: str,
    plan: QueryPlan,
    provider: str,
    raw_results: list[SearchResult],
    decisions: list[SourceDecision],
    used_fallback: bool,
    errors: list[str],
) -> None:
    if trace_path is None:
        return
    try:
        trace_path.parent.mkdir(parents=True, exist_ok=True)
        payload = {
            "created_at": datetime.now(timezone.utc).isoformat(timespec="seconds"),
            "question": question,
            "mode": str(plan.mode),
            "queries": plan.search_queries,
            "provider": provider,
            "used_fallback": used_fallback,
            "required_domains": plan.required_domains,
            "preferred_sources": plan.preferred_sources,
            "excluded_domains": plan.excluded_domains,
            "raw_results": [result.model_dump() for result in raw_results],
            "decisions": [decision.as_dict() for decision in decisions],
            "accepted_count": sum(1 for decision in decisions if decision.status == "accepted"),
            "rejected_count": sum(1 for decision in decisions if decision.status != "accepted"),
            "errors": errors,
        }
        with trace_path.open("a", encoding="utf-8") as handle:
            handle.write(json.dumps(payload, ensure_ascii=False) + "\n")
    except Exception:
        return


def domains_for_tavily(plan: QueryPlan) -> tuple[list[str], list[str]]:
    include_domains: list[str] = []
    if str(plan.mode) == SearchMode.HIGH_RISK.value and plan.required_domains:
        include_domains = list(plan.required_domains)
    elif str(plan.mode) in {SearchMode.SOFTWARE.value, SearchMode.FINANCE.value}:
        include_domains = list(plan.preferred_sources[:8])
    return _dedupe(include_domains), _dedupe([*plan.excluded_domains, *SOCIAL_BLOCKED_DOMAINS])


def domain_from_url(url: str) -> str:
    parsed = urlparse(url if "://" in url else f"https://{url}")
    return parsed.netloc.lower().removeprefix("www.")


def _decision(
    result: SearchResult,
    domain: str,
    status: str,
    reason: str,
    trust_score: float,
) -> SourceDecision:
    return SourceDecision(
        url=result.url,
        title=result.title,
        domain=domain,
        status=status,
        reason=reason,
        trust_score=round(trust_score, 3),
        provider=result.provider,
    )


def _domain_matches(domain: str, patterns: tuple[str, ...] | list[str]) -> bool:
    normalized = domain.lower().removeprefix("www.")
    return any(normalized == pattern or normalized.endswith(f".{pattern}") for pattern in patterns if pattern)


def _looks_like_us_president_query(normalized: str) -> bool:
    return (
        "prezydent" in normalized
        and any(term in normalized for term in ("stanow zjednoczonych", "usa", "us", "united states", "ameryki"))
    )


def _looks_like_richest_query(normalized: str) -> bool:
    return any(term in normalized for term in ("najbogats", "richest", "billionaire", "miliarder"))


def _shares_topic_tokens(question: str, caption: str) -> bool:
    if not caption:
        return False
    question_tokens = {token for token in question.split() if len(token) > 4}
    caption_tokens = set(caption.split())
    return bool(question_tokens & caption_tokens)


def _normalize(text: str) -> str:
    lowered = (text or "").lower()
    lowered = lowered.translate(str.maketrans("ąćęłńóśźż", "acelnoszz"))
    lowered = re.sub(r"[^a-z0-9 ]+", " ", lowered)
    return re.sub(r"\s+", " ", lowered).strip()


def _dedupe(items: list[str] | tuple[str, ...]) -> list[str]:
    seen: set[str] = set()
    unique: list[str] = []
    for item in items:
        normalized = item.strip().lower().removeprefix("www.")
        if not normalized or normalized in seen:
            continue
        seen.add(normalized)
        unique.append(normalized)
    return unique
