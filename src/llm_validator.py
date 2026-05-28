from __future__ import annotations

import json
from typing import Any, Callable

from src.config import Settings
from src.research_models import VisualBrief


ValidatorClient = Callable[[str, str], str]


def validate_research_brief(
    question: str,
    answer: str,
    brief: VisualBrief,
    settings: Settings | None = None,
    llm_client: ValidatorClient | None = None,
) -> dict[str, Any]:
    """Validate whether the visual display matches the answer and evidence.

    The default path is deterministic and local. If validator mode is enabled
    and a client is injected, this can be promoted to an LLM JSON validator
    without adding cost to normal runs or tests.
    """
    base = _heuristic_validation(question, answer, brief)
    if not settings or not getattr(settings, "llm_validator_enabled", False) or not llm_client:
        return base

    prompt = _build_validator_prompt(question, answer, brief)
    try:
        raw = llm_client(getattr(settings, "llm_validator_model", "gpt-4.1-mini"), prompt)
        parsed = json.loads(raw)
    except Exception as error:
        return {
            **base,
            "llm_status": "error",
            "llm_error": str(error),
        }

    confidence = float(parsed.get("confidence", base["confidence"]))
    status = str(parsed.get("status", base["status"]))
    return {
        **base,
        "status": status if status in {"accepted", "uncertain", "rejected"} else base["status"],
        "confidence": round(max(0.0, min(1.0, confidence)), 2),
        "llm_status": "used",
        "llm_reason": str(parsed.get("reason", ""))[:240],
    }


def _heuristic_validation(question: str, answer: str, brief: VisualBrief) -> dict[str, Any]:
    topic = (brief.topic or "").lower()
    answer_lower = (answer or "").lower()
    question_lower = (question or "").lower()
    sources = len(brief.sources)
    images = len(brief.images)
    evidence = len(brief.evidence)
    topic_seen = bool(topic and (topic in answer_lower or topic in question_lower))

    confidence = 0.34
    if topic_seen:
        confidence += 0.18
    confidence += min(0.22, sources * 0.05)
    confidence += min(0.18, evidence * 0.06)
    confidence += min(0.12, images * 0.04)
    confidence = round(min(0.96, confidence), 2)
    status = "accepted" if confidence >= 0.64 and sources else "uncertain"
    if not topic_seen and images:
        status = "rejected"
        confidence = min(confidence, 0.42)

    return {
        "status": status,
        "confidence": confidence,
        "validator": "heuristic",
        "topic_seen_in_answer_or_question": topic_seen,
        "source_count": sources,
        "image_count": images,
        "evidence_count": evidence,
    }


def _build_validator_prompt(question: str, answer: str, brief: VisualBrief) -> str:
    payload = {
        "question": question,
        "answer": answer,
        "brief": {
            "topic": brief.topic,
            "title": brief.title,
            "summary": brief.summary,
            "sources": brief.sources,
            "images": [image.as_dict() for image in brief.images],
            "reports": [report.as_dict() for report in brief.reports],
            "videos": [video.as_dict() for video in brief.videos],
            "claims": [claim.as_dict() for claim in brief.evidence],
        },
    }
    return (
        "Zweryfikuj, czy display JARVISA pasuje do pytania i odpowiedzi. "
        "Zwroc tylko JSON: {\"status\":\"accepted|uncertain|rejected\","
        "\"confidence\":0.0,\"reason\":\"...\"}.\n"
        f"{json.dumps(payload, ensure_ascii=False)}"
    )
