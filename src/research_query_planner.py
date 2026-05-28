from __future__ import annotations

import re
import unicodedata

from src.research_models import ResearchFilters, ResearchQueryPlan


CURRENT_HINTS = {
    "aktualnie",
    "obecnie",
    "dzisiaj",
    "teraz",
    "najnowsze",
    "najbogatszy",
    "ranking",
    "kurs",
    "cena",
    "pogoda",
}

PREFERRED_DOMAINS = [
    "wikipedia.org",
    "wikimedia.org",
    "britannica.com",
    ".gov",
    ".edu",
    "forbes.com",
    "reuters.com",
    "bloomberg.com",
]

RICH_PERSON_DOMAINS = [
    "forbes.com",
    "bloomberg.com",
    "reuters.com",
]

QUERY_STOP_WORDS = {
    "jarvis",
    "pokaz",
    "pokaz mi",
    "powiedz",
    "opowiedz",
    "kto",
    "kim",
    "co",
    "czym",
    "jest",
    "sa",
    "naj",
    "na swiecie",
    "aktualnie",
    "obecnie",
    "prosze",
}


def plan_queries(user_question: str, llm_answer: str | None = None) -> ResearchQueryPlan:
    question = _clean(user_question)
    answer = _clean(llm_answer or "")
    answer_topic = _named_entity_from_text(answer)
    if _is_richest_person_query(question) and not answer_topic:
        return _richest_person_plan()

    topic = answer_topic or _extract_topic(question, answer)
    language = "pl"
    freshness_required = _requires_freshness(question)
    aliases = _build_aliases(topic)
    must_include = aliases[:2] or [topic]
    intent = "entity_research" if _looks_like_person_or_entity(topic) else "topic_research"

    filters = ResearchFilters(
        must_include=must_include,
        entity_aliases=aliases,
        preferred_domains=PREFERRED_DOMAINS,
        freshness_days=14 if freshness_required else None,
        source_type=intent,
    )

    return ResearchQueryPlan(
        topic=topic,
        intent=intent,
        language=language,
        freshness_required=freshness_required,
        web_queries=_dedupe(
            [
                topic,
                f"{topic} najwazniejsze informacje",
                f"{topic} official source",
                f"{topic} latest" if freshness_required else f"{topic} biography facts",
            ]
        ),
        image_queries=_dedupe(
            [
                f"{topic} portrait" if intent == "entity_research" else f"{topic} image",
                f"{topic} official photo",
                f"{topic} Wikimedia Commons",
            ]
        ),
        report_queries=_dedupe(
            [
                f"{topic} report PDF",
                f"{topic} research PDF",
                f"{topic} site:edu OR site:gov",
            ]
        ),
        video_queries=_dedupe(
            [
                f"{topic} documentary",
                f"{topic} interview",
                f"{topic} YouTube official",
            ]
        ),
        filters=filters,
    )


def _extract_topic(question: str, answer: str) -> str:
    answer_topic = _named_entity_from_text(answer)
    if answer_topic:
        return answer_topic

    explicit_question = _topic_from_question(question)
    if explicit_question:
        return explicit_question

    tokens = [
        token
        for token in _normalize(question).split()
        if len(token) > 2 and token not in QUERY_STOP_WORDS
    ]
    return " ".join(tokens[:4]).title() or "Temat"


def _named_entity_from_text(text: str) -> str | None:
    matches = re.findall(r"\b[A-Z][A-Za-z'-]+(?:\s+[A-Z][A-Za-z'-]+){1,3}\b", text or "")
    for match in matches:
        cleaned = _clean_subject(match)
        if cleaned and _looks_like_person_or_entity(cleaned):
            return cleaned
    return None


def _topic_from_question(question: str) -> str | None:
    normalized = question.strip(" ?!.,;:")
    patterns = (
        r"(?:kim|kto)\s+(?:jest|byl|byla)\s+(.+)",
        r"(?:co|czym)\s+(?:jest|sa)\s+(.+)",
        r"(?:opowiedz|powiedz|pokaz)\s+(?:mi\s+)?(?:o|kto jest|kim jest)?\s*(.+)",
        r"pogoda\s+(?:w|dla)?\s*(.+)",
    )
    for pattern in patterns:
        match = re.search(pattern, normalized, flags=re.IGNORECASE)
        if match:
            return _clean_subject(match.group(1))
    return None


def _richest_person_plan() -> ResearchQueryPlan:
    filters = ResearchFilters(
        must_include=["richest", "billionaires"],
        entity_aliases=["richest person", "billionaires", "real time billionaires"],
        preferred_domains=RICH_PERSON_DOMAINS,
        freshness_days=7,
        source_type="current_ranking",
    )
    return ResearchQueryPlan(
        topic="richest person in the world",
        intent="current_ranking",
        language="pl",
        freshness_required=True,
        web_queries=[
            "Forbes Real-Time Billionaires richest person today",
            "Bloomberg Billionaires Index richest person today",
            "Reuters richest person in the world today",
            "richest person in the world today",
        ],
        image_queries=[
            "Forbes Real-Time Billionaires number one portrait",
            "richest person in the world official photo",
        ],
        report_queries=[
            "Forbes Real-Time Billionaires list",
            "Bloomberg Billionaires Index",
        ],
        video_queries=[
            "richest person in the world latest interview",
        ],
        filters=filters,
    )


def _is_richest_person_query(text: str) -> bool:
    normalized = _normalize(text)
    return (
        ("najbogatsz" in normalized and ("czlowiek" in normalized or "osob" in normalized or "swiecie" in normalized))
        or ("richest" in normalized and ("person" in normalized or "people" in normalized))
        or ("billionaires" in normalized and "forbes" in normalized)
    )


def _build_aliases(topic: str) -> list[str]:
    aliases = [topic]
    words = topic.split()
    if len(words) > 1:
        aliases.append(words[-1])
        aliases.append(" ".join(words[:2]))
    return _dedupe([alias for alias in aliases if len(alias) > 2])


def _requires_freshness(text: str) -> bool:
    normalized = _normalize(text)
    return any(hint in normalized for hint in CURRENT_HINTS)


def _looks_like_person_or_entity(topic: str) -> bool:
    words = topic.split()
    return len(words) >= 2 and all(word[:1].isupper() for word in words[:2])


def _clean_subject(subject: str) -> str:
    cleaned = re.sub(r"[?!.,;:]+$", "", subject or "").strip()
    cleaned = re.sub(
        r"\b(wedlug|according|aktualnie|obecnie|teraz|dzisiaj|na swiecie|prosze|szefie|forbes|forbesa)\b",
        "",
        cleaned,
        flags=re.IGNORECASE,
    )
    cleaned = re.sub(r"\s+", " ", cleaned).strip()
    return cleaned[:80]


def _clean(text: str) -> str:
    return re.sub(r"\s+", " ", text or "").strip()


def _normalize(text: str) -> str:
    lowered = unicodedata.normalize("NFKD", (text or "").lower())
    lowered = "".join(character for character in lowered if not unicodedata.combining(character))
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


def _dedupe(items: list[str]) -> list[str]:
    unique = []
    seen = set()
    for item in items:
        cleaned = _clean(item)
        key = cleaned.lower()
        if not cleaned or key in seen:
            continue
        seen.add(key)
        unique.append(cleaned)
    return unique
