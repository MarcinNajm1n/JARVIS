from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any


@dataclass(frozen=True)
class ResearchFilters:
    must_include: list[str] = field(default_factory=list)
    must_not_include: list[str] = field(default_factory=list)
    entity_aliases: list[str] = field(default_factory=list)
    preferred_domains: list[str] = field(default_factory=list)
    freshness_days: int | None = None
    source_type: str = "general"

    def as_dict(self) -> dict[str, Any]:
        return {
            "must_include": self.must_include,
            "must_not_include": self.must_not_include,
            "entity_aliases": self.entity_aliases,
            "preferred_domains": self.preferred_domains,
            "freshness_days": self.freshness_days,
            "source_type": self.source_type,
        }


@dataclass(frozen=True)
class ResearchQueryPlan:
    topic: str
    intent: str
    language: str
    freshness_required: bool
    web_queries: list[str]
    image_queries: list[str]
    report_queries: list[str]
    video_queries: list[str]
    filters: ResearchFilters

    def as_dict(self) -> dict[str, Any]:
        return {
            "topic": self.topic,
            "intent": self.intent,
            "language": self.language,
            "freshness_required": self.freshness_required,
            "queries": {
                "web": self.web_queries,
                "images": self.image_queries,
                "reports": self.report_queries,
                "videos": self.video_queries,
            },
            "filters": self.filters.as_dict(),
        }


@dataclass(frozen=True)
class ImageResult:
    image_url: str
    thumbnail_url: str | None = None
    page_url: str | None = None
    caption: str = ""
    source: str = "web"
    width: int | None = None
    height: int | None = None
    license: str | None = None
    confidence: float = 0.0
    validation: dict[str, Any] = field(default_factory=dict)

    def as_dict(self) -> dict[str, Any]:
        return {
            "image_url": self.image_url,
            "thumbnail_url": self.thumbnail_url,
            "page_url": self.page_url,
            "caption": self.caption,
            "source": self.source,
            "width": self.width,
            "height": self.height,
            "license": self.license,
            "confidence": self.confidence,
            "validation": self.validation,
        }


@dataclass(frozen=True)
class VideoResult:
    title: str
    url: str
    thumbnail_url: str | None = None
    duration: str | None = None
    channel: str | None = None
    published_at: str | None = None
    source: str = "web"
    confidence: float = 0.0
    validation: dict[str, Any] = field(default_factory=dict)

    def as_dict(self) -> dict[str, Any]:
        return {
            "title": self.title,
            "url": self.url,
            "thumbnail_url": self.thumbnail_url,
            "duration": self.duration,
            "channel": self.channel,
            "published_at": self.published_at,
            "source": self.source,
            "confidence": self.confidence,
            "validation": self.validation,
        }


@dataclass(frozen=True)
class ReportResult:
    title: str
    url: str
    file_type: str = "web"
    publisher: str | None = None
    published_at: str | None = None
    snippet: str = ""
    confidence: float = 0.0
    validation: dict[str, Any] = field(default_factory=dict)

    def as_dict(self) -> dict[str, Any]:
        return {
            "title": self.title,
            "url": self.url,
            "file_type": self.file_type,
            "publisher": self.publisher,
            "published_at": self.published_at,
            "snippet": self.snippet,
            "confidence": self.confidence,
            "validation": self.validation,
        }


@dataclass(frozen=True)
class ValidatedEvidence:
    claim: str
    source_url: str
    source_title: str
    confidence: float

    def as_dict(self) -> dict[str, Any]:
        return {
            "claim": self.claim,
            "source_url": self.source_url,
            "source_title": self.source_title,
            "confidence": self.confidence,
        }


@dataclass(frozen=True)
class VisualBrief:
    topic: str
    title: str
    summary: str
    confidence: float
    images: list[ImageResult] = field(default_factory=list)
    videos: list[VideoResult] = field(default_factory=list)
    reports: list[ReportResult] = field(default_factory=list)
    evidence: list[ValidatedEvidence] = field(default_factory=list)
    sources: list[str] = field(default_factory=list)
    validation: dict[str, Any] = field(default_factory=dict)
    trace: dict[str, Any] = field(default_factory=dict)

    def as_visual_payload(self) -> dict[str, Any]:
        media_items = [
            {
                "image_url": image.image_url,
                "caption": image.caption or self.topic,
                "source_url": image.page_url,
                "confidence": image.confidence,
                "fit": (image.validation.get("display") or {}).get("fit", "contain"),
                "position": (image.validation.get("display") or {}).get("position", "center center"),
                "cropping_allowed": bool(
                    (image.validation.get("display") or {}).get("cropping_allowed", False)
                ),
                "validation": image.validation.get("display_validation") or {},
            }
            for image in self.images
        ]
        return {
            "type": "visual_result",
            "mode": "research_brief",
            "presentation": "animated_scene",
            "animation_profile": (
                "low_confidence"
                if self.validation.get("status") == "rejected" or self.confidence < 0.5
                else "result"
            ),
            "ok": self.validation.get("status") != "rejected",
            "topic": self.topic,
            "subject": self.topic,
            "title": self.title,
            "summary": self.summary,
            "message": self.summary,
            "confidence": self.confidence,
            "images": [image.as_dict() for image in self.images],
            "videos": [video.as_dict() for video in self.videos],
            "reports": [report.as_dict() for report in self.reports],
            "claims": [claim.as_dict() for claim in self.evidence],
            "sources": self.sources,
            "media_items": media_items,
            "related_results": [
                {
                    "title": claim.source_title,
                    "url": claim.source_url,
                    "snippet": claim.claim,
                    "source": "validated",
                    "confidence": claim.confidence,
                }
                for claim in self.evidence
            ],
            "validation": self.validation,
            "planner_trace": self.trace,
            "cost": {"operation": "research", "estimated_cost_usd": 0.0},
        }
