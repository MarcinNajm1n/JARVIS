from __future__ import annotations

from enum import StrEnum
from typing import Any, Literal

from pydantic import BaseModel, ConfigDict, Field


class SearchMode(StrEnum):
    NONE = "none"
    WEB = "web"
    NEWS = "news"
    FINANCE = "finance"
    SOFTWARE = "software"
    OFFICIAL = "official"
    HIGH_RISK = "high_risk"


class QueryPlan(BaseModel):
    model_config = ConfigDict(use_enum_values=True)

    original_question: str
    needs_realtime: bool
    mode: SearchMode = SearchMode.NONE
    search_queries: list[str] = Field(default_factory=list)
    preferred_sources: list[str] = Field(default_factory=list)
    required_domains: list[str] = Field(default_factory=list)
    excluded_domains: list[str] = Field(default_factory=list)
    reason: str = ""
    min_sources: int = 1
    min_trusted_sources: int = 1
    requires_official_source: bool = False
    freshness_required: bool = False


class SearchResult(BaseModel):
    title: str
    url: str
    snippet: str | None = None
    provider: str
    published_at: str | None = None
    score: float | None = None
    image_url: str | None = None


class FetchedSource(BaseModel):
    title: str
    url: str
    provider: str
    raw_snippet: str | None = None
    extracted_text: str = ""
    published_at: str | None = None
    trust_score: float = 0.0
    fetch_error: str | None = None


class EvidenceChunk(BaseModel):
    source_url: str
    source_title: str
    text: str
    relevance_score: float
    trust_score: float


class OperationEvent(BaseModel):
    name: str
    status: Literal["pending", "running", "done", "failed", "skipped"] = "done"
    duration_ms: int = 0
    detail: str | None = None


class JarvisAnswer(BaseModel):
    answer: str
    spoken_answer: str
    confidence: Literal["high", "medium", "low"] = "medium"
    display_type: str = "jarvis_tactical_hud"
    checked_at: str
    sources: list[dict[str, Any]] = Field(default_factory=list)
    operations: list[dict[str, Any]] = Field(default_factory=list)
    visual_assets: list[dict[str, Any]] = Field(default_factory=list)


class RetrievalResult(BaseModel):
    model_config = ConfigDict(use_enum_values=True)

    question: str
    checked_at: str
    plan: QueryPlan
    search_results: list[SearchResult] = Field(default_factory=list)
    fetched_sources: list[FetchedSource] = Field(default_factory=list)
    evidence: list[EvidenceChunk] = Field(default_factory=list)
    operations: list[OperationEvent] = Field(default_factory=list)
    visual_assets: list[dict[str, Any]] = Field(default_factory=list)
    used_fallback: bool = False
    errors: list[str] = Field(default_factory=list)
    rejected_results: list[dict[str, Any]] = Field(default_factory=list)

    @property
    def has_evidence(self) -> bool:
        return bool(self.evidence)

    def confidence_label(self) -> Literal["high", "medium", "low"]:
        if not self.evidence:
            return "low"
        trusted_sources = {
            chunk.source_url
            for chunk in self.evidence
            if chunk.trust_score >= 0.62 and chunk.relevance_score >= 0.45
        }
        if self.plan.mode == SearchMode.HIGH_RISK.value and len(trusted_sources) < self.plan.min_trusted_sources:
            return "low"
        if len(trusted_sources) >= 3:
            return "high"
        if len(trusted_sources) >= 1:
            return "medium"
        return "low"

    def context_for_llm(self, max_chunks: int = 5) -> str:
        if not self.evidence:
            return "Brak zweryfikowanych fragmentow zrodel."
        lines = []
        for index, chunk in enumerate(self.evidence[:max_chunks], start=1):
            lines.append(
                "\n".join(
                    [
                        f"[{index}] Tytul: {chunk.source_title}",
                        f"URL: {chunk.source_url}",
                        f"Trust: {chunk.trust_score:.2f}; Relevance: {chunk.relevance_score:.2f}",
                        f"Fragment: {chunk.text}",
                    ]
                )
            )
        return "\n\n".join(lines)

    def source_payloads(self) -> list[dict[str, Any]]:
        payloads = []
        seen = set()
        for chunk in self.evidence:
            if chunk.source_url in seen:
                continue
            seen.add(chunk.source_url)
            payloads.append(
                {
                    "title": chunk.source_title,
                    "url": chunk.source_url,
                    "summary": chunk.text[:280],
                    "provider": _provider_for_url(chunk.source_url, self.fetched_sources),
                    "trust_score": round(chunk.trust_score, 2),
                    "relevance_score": round(chunk.relevance_score, 2),
                }
            )
        return payloads

    def fallback_answer(self) -> JarvisAnswer:
        if self.evidence:
            answer = (
                "Mam zweryfikowane zrodla, ale model nie zwrocil poprawnego JSON. "
                "Pokazuje najlepsze fragmenty w panelu HUD."
            )
            spoken = "Mam zrodla, ale odpowiedz strukturalna wymaga korekty."
            confidence = self.confidence_label()
        else:
            answer = (
                "Nie mam wystarczajaco wiarygodnych danych z internetu, zeby bezpiecznie "
                "odpowiedziec na to pytanie."
            )
            spoken = "Nie moge teraz wiarygodnie zweryfikowac tego w internecie."
            confidence = "low"

        return JarvisAnswer(
            answer=answer,
            spoken_answer=spoken,
            confidence=confidence,
            checked_at=self.checked_at,
            sources=self.source_payloads(),
            operations=[operation.model_dump() for operation in self.operations],
            visual_assets=self.visual_assets,
        )


class RetrievalError(RuntimeError):
    def __init__(self, message: str, *, rate_limited: bool = False) -> None:
        super().__init__(message)
        self.rate_limited = rate_limited


def _provider_for_url(url: str, sources: list[FetchedSource]) -> str:
    for source in sources:
        if source.url == url:
            return source.provider
    return "web"
