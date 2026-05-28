from __future__ import annotations

from typing import Any

from src.display.hud_models import HUDPayload
from src.display.search_payload import normalize_search_payload
from src.retrieval.models import JarvisAnswer


def build_display_payload(answer: JarvisAnswer | dict[str, Any], question: str = "") -> dict[str, Any]:
    jarvis_answer = answer if isinstance(answer, JarvisAnswer) else JarvisAnswer.model_validate(answer)
    ok = jarvis_answer.confidence != "low" or bool(jarvis_answer.sources)
    payload = HUDPayload(
        question=question,
        answer=jarvis_answer.answer,
        spoken_answer=_strip_links(jarvis_answer.spoken_answer),
        confidence=jarvis_answer.confidence,
        animation_profile="low_confidence" if not ok else "result",
        checked_at=jarvis_answer.checked_at,
        operations=jarvis_answer.operations,
        sources=jarvis_answer.sources,
        visual_assets=jarvis_answer.visual_assets,
        normalized_results=normalize_search_payload(
            {
                "query": question,
                "answer": jarvis_answer.answer,
                "sources": jarvis_answer.sources,
                "results": jarvis_answer.sources,
            }
        ),
        message=jarvis_answer.answer,
        ok=ok,
    )
    return payload.model_dump()


def display(payload: str | dict[str, Any] | JarvisAnswer) -> dict[str, Any]:
    """Backward-compatible display wrapper.

    The web UI consumes this dict through the existing VISUAL_RESULT event. A
    plain string still works and becomes a static HUD message.
    """
    if isinstance(payload, str):
        return {
            "type": "visual_result",
            "mode": "jarvis_tactical_hud",
            "display_type": "jarvis_tactical_hud",
            "presentation": "animated_scene",
            "animation_profile": "result",
            "answer": payload,
            "spoken_answer": _strip_links(payload),
            "message": payload,
            "confidence": "medium",
            "operations": [],
            "sources": [],
            "visual_assets": [],
            "normalized_results": normalize_search_payload(payload),
            "ok": True,
        }
    if isinstance(payload, JarvisAnswer):
        return build_display_payload(payload)
    if payload.get("display_type") == "jarvis_tactical_hud" or payload.get("mode") == "jarvis_tactical_hud":
        payload = dict(payload)
        payload["spoken_answer"] = _strip_links(str(payload.get("spoken_answer") or ""))
        payload.setdefault("presentation", "animated_scene")
        payload.setdefault("animation_profile", "low_confidence" if payload.get("ok") is False else "result")
        payload.setdefault("normalized_results", normalize_search_payload(payload))
        return payload
    return dict(payload)


def _strip_links(text: str) -> str:
    import re

    return re.sub(r"https?://\S+|www\.\S+", "", text or "").strip()
