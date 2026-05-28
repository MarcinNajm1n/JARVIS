from __future__ import annotations

from typing import Any

from pydantic import BaseModel, Field


class HUDPayload(BaseModel):
    type: str = "visual_result"
    mode: str = "jarvis_tactical_hud"
    display_type: str = "jarvis_tactical_hud"
    presentation: str = "animated_scene"
    animation_profile: str = "result"
    question: str = ""
    answer: str = ""
    spoken_answer: str = ""
    confidence: str = "medium"
    checked_at: str = ""
    operations: list[dict[str, Any]] = Field(default_factory=list)
    sources: list[dict[str, Any]] = Field(default_factory=list)
    visual_assets: list[dict[str, Any]] = Field(default_factory=list)
    normalized_results: list[dict[str, Any]] = Field(default_factory=list)
    message: str = ""
    ok: bool = True
