from __future__ import annotations

from dataclasses import replace

from src.research_models import ImageResult
from src.voice_commands import normalize_voice_command


DEFAULT_DISPLAY = {
    "fit": "contain",
    "position": "center center",
    "background": "dark",
    "cropping_allowed": False,
}


def prepare_display_images(
    images: list[ImageResult],
    topic: str,
    limit: int = 4,
) -> list[ImageResult]:
    prepared = []
    seen = set()
    for image in images:
        if not image.image_url:
            continue
        key = image.image_url.lower()
        if key in seen:
            continue
        seen.add(key)
        display_validation = validate_image_display(image, topic)
        if display_validation["status"] != "accepted":
            continue
        validation = {
            **image.validation,
            "display": DEFAULT_DISPLAY,
            "display_validation": display_validation,
        }
        prepared.append(replace(image, validation=validation))
        if len(prepared) >= limit:
            break
    return prepared


def validate_image_display(image: ImageResult, topic: str) -> dict:
    evidence = " ".join(
        [
            image.caption or "",
            image.page_url or "",
            image.source or "",
            image.image_url or "",
        ]
    )
    topic_ok = _topic_matches(topic, evidence)
    if not topic_ok:
        return {
            "status": "rejected",
            "reason": "image_topic_mismatch",
            "cropping_allowed": False,
        }
    if _looks_like_small_asset(image):
        return {
            "status": "rejected",
            "reason": "image_too_small_or_asset_like",
            "cropping_allowed": False,
        }
    return {
        "status": "accepted",
        "reason": "topic_match_display_safe",
        "fit": "contain",
        "cropping_allowed": False,
        "visible_subject_expected": True,
    }


def media_item_from_image(image: ImageResult, fallback_caption: str) -> dict:
    display = image.validation.get("display") or DEFAULT_DISPLAY
    return {
        "image_url": image.image_url,
        "caption": image.caption or fallback_caption,
        "source_url": image.page_url,
        "confidence": image.confidence,
        "fit": display.get("fit", "contain"),
        "position": display.get("position", "center center"),
        "cropping_allowed": bool(display.get("cropping_allowed", False)),
        "validation": image.validation.get("display_validation") or {},
    }


def _topic_matches(topic: str, evidence: str) -> bool:
    normalized_topic = normalize_voice_command(topic)
    normalized_evidence = normalize_voice_command(evidence)
    if not normalized_topic or not normalized_evidence:
        return False
    if normalized_topic in normalized_evidence:
        return True
    tokens = [token for token in normalized_topic.split() if len(token) > 2]
    return bool(tokens) and all(token in normalized_evidence for token in tokens)


def _looks_like_small_asset(image: ImageResult) -> bool:
    if image.width is None or image.height is None:
        return False
    if image.width < 220 or image.height < 180:
        return True
    ratio = image.width / max(1, image.height)
    return ratio > 5 or ratio < 0.18
