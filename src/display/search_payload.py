from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any
from urllib.parse import urlparse


VISUAL_IMAGE_KEYS = (
    "image",
    "imageUrl",
    "image_url",
    "preview",
    "previewImage",
    "preview_image",
    "ogImage",
    "og_image",
    "openGraphImage",
    "open_graph_image",
)
VISUAL_THUMBNAIL_KEYS = ("thumbnail", "thumbnailUrl", "thumbnail_url")
VISUAL_FAVICON_KEYS = ("favicon", "faviconUrl", "favicon_url", "icon")
VISUAL_COLLECTION_KEYS = ("media", "images", "attachments", "visual_assets")


@dataclass(frozen=True)
class NormalizedSearchResult:
    id: str
    title: str
    summary: str = ""
    url: str = ""
    source: str = ""
    date: str = ""
    score: float | None = None
    kind: str = "result"
    imageUrl: str = ""
    thumbnailUrl: str = ""
    faviconUrl: str = ""
    media: list[dict[str, Any]] = field(default_factory=list)
    raw: Any = None

    def as_dict(self) -> dict[str, Any]:
        return {
            "id": self.id,
            "title": self.title,
            "summary": self.summary,
            "url": self.url,
            "source": self.source,
            "date": self.date,
            "score": self.score,
            "kind": self.kind,
            "imageUrl": self.imageUrl,
            "thumbnailUrl": self.thumbnailUrl,
            "faviconUrl": self.faviconUrl,
            "media": self.media,
            "raw": self.raw,
        }


def normalize_search_payload(payload: Any, limit: int = 12) -> list[dict[str, Any]]:
    results = _normalize(payload, limit=limit)
    if results:
        return [result.as_dict() for result in results[:limit]]
    return [
        NormalizedSearchResult(
            id="debug-empty",
            title="NO SEARCH RESULTS RECEIVED",
            summary=_diagnostic_summary(payload),
            kind="debug",
            raw=_safe_preview(payload),
        ).as_dict()
    ]


def _normalize(payload: Any, limit: int) -> list[NormalizedSearchResult]:
    if payload is None:
        return []
    if isinstance(payload, str):
        return [
            NormalizedSearchResult(
                id="string-0",
                title=_compact(payload, 80) or "Text payload",
                summary=_compact(payload, 320),
                kind="answer",
                raw=payload,
            )
        ]
    if isinstance(payload, list):
        return [
            _result_from_mapping(item if isinstance(item, dict) else {"title": str(item)}, index, "result")
            for index, item in enumerate(payload[:limit])
        ]
    if not isinstance(payload, dict):
        return []

    if isinstance(payload.get("results"), list):
        return [
            _result_from_mapping(item, index, "result")
            for index, item in enumerate(payload["results"][:limit])
        ]

    if isinstance(payload.get("items"), list):
        return [
            _result_from_mapping(item, index, "result")
            for index, item in enumerate(payload["items"][:limit])
        ]

    if isinstance(payload.get("nodes"), list) or isinstance(payload.get("edges"), list):
        graph_items: list[NormalizedSearchResult] = []
        for index, node in enumerate((payload.get("nodes") or [])[:limit]):
            graph_items.append(_result_from_mapping(node, index, "node"))
        remaining = max(0, limit - len(graph_items))
        for index, edge in enumerate((payload.get("edges") or [])[:remaining]):
            graph_items.append(_result_from_mapping(edge, index, "edge"))
        return graph_items

    answer = str(payload.get("answer") or payload.get("message") or payload.get("summary") or "").strip()
    sources = payload.get("sources") if isinstance(payload.get("sources"), list) else []
    if answer or sources:
        visual = extract_visual_assets(payload)
        normalized = []
        if answer:
            normalized.append(
                NormalizedSearchResult(
                    id="answer-0",
                    title=_compact(payload.get("title") or payload.get("question") or "Odpowiedz JARVISA", 90),
                    summary=_compact(answer, 420),
                    kind="answer",
                    imageUrl=visual["imageUrl"],
                    thumbnailUrl=visual["thumbnailUrl"],
                    faviconUrl=visual["faviconUrl"],
                    media=visual["media"],
                    raw={"answer": answer},
                )
            )
        for index, source in enumerate(sources[: max(0, limit - len(normalized))]):
            normalized.append(_result_from_mapping(source, index, "source"))
        return normalized

    known = [
        key
        for key in ("title", "subject", "topic", "query", "error")
        if payload.get(key)
    ]
    if known:
        return [_result_from_mapping(payload, 0, "debug")]

    return []


def _result_from_mapping(item: Any, index: int, kind: str) -> NormalizedSearchResult:
    if not isinstance(item, dict):
        item = {"title": str(item)}
    visual = extract_visual_assets(item)
    title = (
        item.get("title")
        or item.get("name")
        or item.get("label")
        or item.get("source_title")
        or item.get("id")
        or f"{kind.title()} {index + 1}"
    )
    summary = (
        item.get("summary")
        or item.get("snippet")
        or item.get("description")
        or item.get("text")
        or item.get("claim")
        or item.get("metadata")
        or ""
    )
    url = str(item.get("url") or item.get("source_url") or item.get("page_url") or "")
    source = _source_value(item.get("source")) or str(item.get("provider") or _domain(url) or "")
    score = item.get("score") or item.get("confidence") or item.get("trust_score")
    return NormalizedSearchResult(
        id=str(item.get("id") or f"{kind}-{index}"),
        title=_compact(str(title), 110),
        summary=_compact(_stringify(summary), 420),
        url=url,
        source=_compact(source, 80),
        date=str(item.get("date") or item.get("published_at") or item.get("checked_at") or ""),
        score=_score_or_none(score),
        kind=kind,
        imageUrl=visual["imageUrl"],
        thumbnailUrl=visual["thumbnailUrl"],
        faviconUrl=visual["faviconUrl"],
        media=visual["media"],
        raw=_safe_preview(item),
    )


def extract_visual_assets(item: Any) -> dict[str, Any]:
    if not isinstance(item, dict):
        return {"imageUrl": "", "thumbnailUrl": "", "faviconUrl": "", "media": []}

    image_url = _first_url(item, VISUAL_IMAGE_KEYS)
    thumbnail_url = _first_url(item, VISUAL_THUMBNAIL_KEYS)
    favicon_url = _first_url(item, VISUAL_FAVICON_KEYS)
    media: list[dict[str, Any]] = []

    for key in VISUAL_COLLECTION_KEYS:
        media.extend(_media_entries(item.get(key)))

    if image_url:
        media.insert(
            0,
            {
                "type": "image",
                "url": image_url,
                "alt": _compact(item.get("title") or item.get("name") or item.get("label") or "", 120),
            },
        )
    if thumbnail_url and thumbnail_url != image_url:
        media.append(
            {
                "type": "image",
                "url": thumbnail_url,
                "alt": _compact(item.get("title") or item.get("name") or item.get("label") or "", 120),
            }
        )

    media = _dedupe_media(media)
    if not favicon_url:
        url = str(item.get("url") or item.get("source_url") or item.get("page_url") or "")
        favicon_url = _favicon_for_url(url)

    return {
        "imageUrl": image_url,
        "thumbnailUrl": thumbnail_url,
        "faviconUrl": favicon_url,
        "media": media,
    }


def _first_url(item: dict[str, Any], keys: tuple[str, ...]) -> str:
    for key in keys:
        value = item.get(key)
        url = _extract_url(value)
        if url:
            return url
    return ""


def _extract_url(value: Any) -> str:
    if not value:
        return ""
    if isinstance(value, str):
        return value.strip()
    if isinstance(value, dict):
        for key in ("url", "src", "href", "image_url", "imageUrl", "thumbnail_url", "thumbnailUrl"):
            url = _extract_url(value.get(key))
            if url:
                return url
    if isinstance(value, list):
        for item in value:
            url = _extract_url(item)
            if url:
                return url
    return ""


def _media_entries(value: Any) -> list[dict[str, Any]]:
    if not value:
        return []
    items = value if isinstance(value, list) else [value]
    entries: list[dict[str, Any]] = []
    for item in items:
        if isinstance(item, str):
            entries.append({"type": _media_type(item), "url": item})
            continue
        if not isinstance(item, dict):
            continue
        url = _extract_url(item)
        if not url:
            continue
        entry: dict[str, Any] = {
            "type": str(item.get("type") or item.get("kind") or _media_type(url)),
            "url": url,
        }
        if item.get("alt") or item.get("caption") or item.get("title"):
            entry["alt"] = _compact(item.get("alt") or item.get("caption") or item.get("title"), 140)
        if item.get("width") is not None:
            entry["width"] = item.get("width")
        if item.get("height") is not None:
            entry["height"] = item.get("height")
        entries.append(entry)
    return entries


def _dedupe_media(items: list[dict[str, Any]]) -> list[dict[str, Any]]:
    seen: set[str] = set()
    unique: list[dict[str, Any]] = []
    for item in items:
        url = str(item.get("url") or "")
        if not url or url in seen:
            continue
        seen.add(url)
        media_type = str(item.get("type") or "unknown").lower()
        if media_type not in {"image", "video", "unknown"}:
            media_type = "image" if media_type.startswith("image") else "video" if media_type.startswith("video") else "unknown"
        unique.append({**item, "type": media_type})
    return unique


def _media_type(url: str) -> str:
    path = urlparse(url).path.lower()
    if path.endswith((".png", ".jpg", ".jpeg", ".webp", ".gif", ".avif", ".svg")):
        return "image"
    if path.endswith((".mp4", ".webm", ".mov")):
        return "video"
    return "unknown"


def _favicon_for_url(url: str) -> str:
    domain = _domain(url)
    if not domain:
        return ""
    return f"https://www.google.com/s2/favicons?domain={domain}&sz=64"


def _score_or_none(value: Any) -> float | None:
    try:
        return float(value)
    except (TypeError, ValueError):
        return None


def _source_value(value: Any) -> str:
    if isinstance(value, str):
        return value
    if not isinstance(value, dict):
        return ""
    source_url = str(value.get("url") or value.get("source_url") or "")
    if value.get("title") and source_url:
        return f"{value['title']} ({_domain(source_url) or source_url})"
    if value.get("title"):
        return str(value["title"])
    if source_url:
        return _domain(source_url) or source_url
    if value.get("provider"):
        return str(value["provider"])
    return _stringify(value)


def _domain(url: str) -> str:
    if not url:
        return ""
    parsed = urlparse(url)
    return parsed.netloc.replace("www.", "") if parsed.netloc else url


def _diagnostic_summary(payload: Any) -> str:
    if payload is None:
        return "Payload received but it was null."
    if isinstance(payload, dict):
        keys = ", ".join(sorted(str(key) for key in payload.keys())[:10])
        return f"Payload received but no renderable fields found. Keys: {keys or 'none'}."
    return f"Invalid payload format: {type(payload).__name__}."


def _safe_preview(value: Any) -> Any:
    if isinstance(value, dict):
        return {str(key): _safe_preview(item) for key, item in list(value.items())[:16]}
    if isinstance(value, list):
        return [_safe_preview(item) for item in value[:8]]
    if isinstance(value, (str, int, float, bool)) or value is None:
        return value
    return str(value)


def _stringify(value: Any) -> str:
    if isinstance(value, str):
        return value
    if value is None:
        return ""
    if isinstance(value, dict):
        return "; ".join(f"{key}: {item}" for key, item in list(value.items())[:6])
    if isinstance(value, list):
        return "; ".join(str(item) for item in value[:6])
    return str(value)


def _compact(text: Any, limit: int) -> str:
    cleaned = " ".join(str(text or "").split())
    if len(cleaned) <= limit:
        return cleaned
    return cleaned[: max(0, limit - 3)].rstrip() + "..."
