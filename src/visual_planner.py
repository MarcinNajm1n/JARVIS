from __future__ import annotations

import json
import re
import unicodedata
import urllib.parse
import urllib.request
from dataclasses import dataclass, field
from typing import Callable, Any

from src.research_orchestrator import build_research_brief
from src.web_search import WebSearchBundle, search_web
from src.search_service import validate_search_results
from src.weather_service import is_weather_query


WIKIPEDIA_SEARCH_URL = "https://pl.wikipedia.org/w/api.php"
WIKIPEDIA_SUMMARY_URL = "https://pl.wikipedia.org/api/rest_v1/page/summary"

FACTUAL_QUESTION_HINTS = (
    "kto jest",
    "kim jest",
    "co to jest",
    "czym jest",
    "opowiedz o",
    "powiedz o",
    "najbogatszy",
    "najwiekszy",
    "najszybszy",
    "prezydent",
    "premier",
    "ceo",
    "firma",
    "osoba",
    "wynalazl",
    "zalozyl",
)

SUBJECT_TOKEN_RE = re.compile(r"\b[^\W\d_][\w'-]*(?:\s+[^\W\d_][\w'-]*){0,3}\b", re.UNICODE)

STOP_SUBJECT_WORDS = {
    "nie",
    "brak",
    "niestety",
    "jest",
    "sa",
    "byl",
    "byla",
    "bylo",
    "to",
    "ten",
    "ta",
    "te",
    "jeden",
    "jedna",
    "jedno",
    "wedlug",
    "obecnie",
    "najprawdopodobniej",
    "prawdopodobnie",
    "aktualnie",
    "forbesa",
    "forbes",
    "według",
    "źródeł",
    "zrodel",
}

SUBJECT_LEADING_WORDS = {
    "nie",
    "brak",
    "niestety",
    "wedlug",
    "obecnie",
    "najprawdopodobniej",
    "prawdopodobnie",
    "aktualnie",
    "dzisiaj",
    "moim",
    "zdaniem",
    "forbes",
    "forbesa",
}

UNCERTAIN_ANSWER_HINTS = (
    "nie mam wystarczajaco pewnych aktualnych danych",
    "nie mam wystarczajaco pewnych danych",
    "brak pewnych zrodel",
    "brak zweryfikowanych zrodel",
    "nie moge jednoznacznie okreslic",
    "nie jestem w stanie jednoznacznie okreslic",
)

STRUCTURED_MODAL_HINTS = (
    "rachunek",
    "rachunki",
    "faktura",
    "faktury",
    "koszt",
    "koszty",
    "budzet",
    "budzety",
    "oplata",
    "oplaty",
    "czynsz",
    "abonament",
    "paragon",
    "wydatki",
    "wydatek",
)

AMOUNT_WITH_CURRENCY_RE = re.compile(
    r"(?P<amount>\d+(?:[ .]\d{3})*(?:[,.]\d{1,2})?)\s*(?P<currency>pln|z(?:l|ł)|eur|usd|gbp)\b",
    re.IGNORECASE,
)

DUE_DATE_RE = re.compile(
    r"(?:termin|platne|płatne|do)\s*:?\s*(?P<due>\d{1,2}[.-]\d{1,2}(?:[.-]\d{2,4})?)",
    re.IGNORECASE,
)


@dataclass(frozen=True)
class EntityProfile:
    title: str
    summary: str
    image_url: str | None = None
    source_url: str | None = None
    facts: list[str] = field(default_factory=list)
    related_results: list[dict[str, Any]] = field(default_factory=list)
    ok: bool = True
    source: str = "Wikipedia"
    error: str | None = None

    def to_visual_payload(self, answer: str | None = None) -> dict[str, Any]:
        facts = self.facts or _extract_facts(answer or self.summary)
        return {
            "type": "visual_result",
            "mode": "entity_profile",
            "presentation": "animated_scene",
            "animation_profile": "result" if self.ok else "low_confidence",
            "ok": self.ok,
            "title": self.title,
            "subject": self.title,
            "summary": self.summary or _compact(answer or "", 360),
            "image_url": self.image_url,
            "facts": facts[:5],
            "related_results": self.related_results[:4],
            "sources": [self.source_url or self.source] if self.source_url else [self.source],
            "cost": {"operation": "visual_planner", "estimated_cost_usd": 0.0},
            "message": self.summary or _compact(answer or "", 360),
            "error": self.error,
        }


ProfileLookup = Callable[[str], EntityProfile | None]
WebSearch = Callable[[str], WebSearchBundle]


def plan_visual_result(
    question: str,
    answer: str,
    lookup: ProfileLookup | None = None,
    web_search: WebSearch | None = None,
    search_bundle: WebSearchBundle | None = None,
) -> dict[str, Any] | None:
    """Return a generic visual display plan for factual answers.

    The planner is intentionally conservative: weather stays on the dedicated
    weather display path, while general factual prompts can become an
    entity_profile card backed by Wikipedia data.
    """
    question = (question or "").strip()
    answer = (answer or "").strip()
    if not question or not answer:
        return None
    if is_weather_query(question):
        return None
    if _looks_structured_modal_query(question, answer):
        return _structured_modal_payload(question, answer)
    if _is_uncertain_answer(answer):
        return None
    if not _looks_factual(question, answer):
        return None

    if search_bundle is not None and search_bundle.results:
        research_provider = None
        if web_search is not None:
            research_provider = lambda query, _timeout, _limit: web_search(query)
        research_payload = build_research_brief(
            question,
            answer,
            search_bundle=search_bundle,
            search_provider=research_provider,
        )
        if research_payload is not None:
            return research_payload

    subject, trace = _select_visual_subject(question, answer)
    search_fn = web_search or search_web
    if not subject:
        return None

    trace["search_query"] = subject
    lookup_fn = lookup or lookup_entity_profile
    blocked_mismatch = False
    profile = lookup_fn(subject)
    if profile is not None and not _profile_matches_subject(profile, subject):
        trace["validation"] = "profile_title_mismatch"
        trace["rejected_subject"] = profile.title
        blocked_mismatch = True
        profile = None

    web_results = search_bundle or WebSearchBundle(query=subject)
    if profile is None or profile.ok is False:
        if not web_results.results:
            web_results = search_fn(subject)
        web_results = _filter_search_results(web_results, subject)
        trace["search_query"] = web_results.query or subject
        if web_results.best:
            profile = _profile_from_web_results(subject, answer, web_results)

    if profile is not None and not _profile_matches_subject(profile, subject):
        trace["validation"] = "web_result_mismatch"
        trace["rejected_subject"] = profile.title
        return _uncertain_visual_payload(question, answer, trace)

    if profile is None and blocked_mismatch:
        trace["validation"] = "profile_title_mismatch"
        return _uncertain_visual_payload(question, answer, trace)

    if profile is None:
        profile = EntityProfile(
            ok=True,
            title=subject,
            summary=_compact(answer, 360),
            facts=_extract_facts(answer),
            related_results=web_results.as_payload_results(),
            source="JARVIS answer",
        )

    payload = profile.to_visual_payload(answer)
    payload["query"] = question
    trace["validation"] = trace.get("validation") or "subject_confirmed"
    payload["planner_trace"] = trace
    payload["related_results"] = _merge_related_results(
        payload.get("related_results") or [],
        web_results.as_payload_results(),
    )
    payload["media_items"] = _media_items_from_payload(payload)
    payload["validation"] = validate_search_results(question, answer, web_results).as_dict()
    if len(payload["media_items"]) > 1:
        payload["mode"] = "entity_gallery"
    return payload


def extract_visual_subject(question: str, answer: str) -> str | None:
    if _is_uncertain_answer(answer):
        return None
    subject, _trace = _select_visual_subject(question, answer)
    if subject:
        return subject
    explicit = _extract_subject_from_question(question)
    if explicit and _looks_like_named_entity(explicit):
        return explicit
    return explicit


def _select_visual_subject(question: str, answer: str) -> tuple[str | None, dict[str, Any]]:
    answer_candidates = _extract_subject_candidates_from_answer(answer)
    explicit = _extract_subject_from_question(question)
    trace: dict[str, Any] = {
        "question": _compact(question, 180),
        "answer_excerpt": _compact(answer, 260),
        "candidate_subjects": [candidate["subject"] for candidate in answer_candidates],
        "selected_subject": None,
        "selection_source": "none",
        "confidence": 0.0,
        "search_query": None,
    }

    if explicit and _looks_like_named_entity(explicit) and _subject_in_text(explicit, answer):
        trace.update(
            {
                "selected_subject": explicit,
                "selection_source": "question_named_entity_confirmed_by_answer",
                "confidence": 0.92,
            }
        )
        return explicit, trace

    if answer_candidates:
        best = answer_candidates[0]
        trace.update(
            {
                "selected_subject": best["subject"],
                "selection_source": "answer",
                "confidence": best["confidence"],
            }
        )
        return best["subject"], trace

    trace["validation"] = "no_answer_entity"
    return None, trace


def lookup_entity_profile(subject: str, timeout: float = 4.0) -> EntityProfile | None:
    clean_subject = _clean_subject(subject)
    if not clean_subject:
        return None

    title = _search_wikipedia_title(clean_subject, timeout=timeout) or clean_subject
    try:
        summary = _fetch_wikipedia_summary(title, timeout=timeout)
    except Exception as error:
        return EntityProfile(
            ok=False,
            title=clean_subject,
            summary=f"Nie mam aktualnego profilu encji dla: {clean_subject}.",
            source="Wikipedia",
            error=str(error),
        )

    extract = str(summary.get("extract") or "").strip()
    if not extract:
        return None

    thumbnail = summary.get("thumbnail") or {}
    content_urls = summary.get("content_urls") or {}
    desktop = content_urls.get("desktop") or {}
    return EntityProfile(
        ok=True,
        title=str(summary.get("title") or title).strip(),
        summary=_compact(extract, 420),
        image_url=thumbnail.get("source"),
        source_url=desktop.get("page"),
        facts=_extract_facts(extract),
        source="Wikipedia",
    )


def _profile_from_web_results(
    subject: str,
    answer: str,
    web_results: WebSearchBundle,
) -> EntityProfile | None:
    best = web_results.best
    if best is None:
        return None
    summary = best.snippet or _compact(answer, 420)
    return EntityProfile(
        ok=True,
        title=best.title or subject,
        summary=_compact(summary, 420),
        image_url=best.image_url,
        source_url=best.url,
        facts=_extract_facts(summary or answer),
        related_results=web_results.as_payload_results(),
        source=best.source,
    )


def _merge_related_results(left: list[dict[str, Any]], right: list[dict[str, Any]]) -> list[dict[str, Any]]:
    merged = []
    seen = set()
    for item in [*left, *right]:
        key = (str(item.get("title") or "").lower(), str(item.get("url") or "").lower())
        if not key[0] or key in seen:
            continue
        seen.add(key)
        merged.append(item)
    return merged[:6]


def _media_items_from_payload(payload: dict[str, Any]) -> list[dict[str, Any]]:
    media_items = []
    seen_images = set()
    if payload.get("image_url"):
        seen_images.add(payload["image_url"])
        media_items.append(
            {
                "image_url": payload["image_url"],
                "caption": payload.get("title") or payload.get("subject") or "Wynik",
                "source_url": (payload.get("sources") or [None])[0],
            }
        )
    for item in payload.get("related_results") or []:
        image_url = item.get("image_url")
        if not image_url or image_url in seen_images:
            continue
        seen_images.add(image_url)
        media_items.append(
            {
                "image_url": image_url,
                "caption": item.get("title") or "Wynik",
                "source_url": item.get("url"),
            }
        )
        if len(media_items) >= 4:
            break
    return media_items


def _uncertain_visual_payload(question: str, answer: str, trace: dict[str, Any]) -> dict[str, Any]:
    subject = trace.get("selected_subject") or "niepewny temat"
    reason = trace.get("validation") or "subject_mismatch"
    return {
        "type": "visual_result",
        "mode": "generic",
        "presentation": "animated_scene",
        "animation_profile": "low_confidence",
        "ok": False,
        "title": "Brak pewnego displaya",
        "subject": subject,
        "summary": (
            "Nie pokazuje profilu, bo zrodlo wizualne nie pasuje do odpowiedzi JARVISA."
        ),
        "message": _compact(answer, 360),
        "facts": [_compact(answer, 180)] if answer else [],
        "related_results": [],
        "sources": ["JARVIS answer"],
        "cost": {"operation": "visual_planner", "estimated_cost_usd": 0.0},
        "query": question,
        "error": reason,
        "planner_trace": trace,
    }


def _looks_structured_modal_query(question: str, answer: str) -> bool:
    normalized = _normalize(f"{question} {answer}")
    return any(hint in normalized for hint in STRUCTURED_MODAL_HINTS)


def _structured_modal_payload(question: str, answer: str) -> dict[str, Any]:
    rows, detected_currency = _extract_structured_rows(answer)
    total = _extract_total(answer)
    if total is None and rows:
        total = round(sum(row["numeric_amount"] for row in rows), 2)
    public_rows = [
        {
            "item": row["item"],
            "amount": row["amount"],
            "due": row["due"],
        }
        for row in rows
    ]
    ok = not _is_uncertain_answer(answer)
    return {
        "type": "visual_result",
        "mode": "structured_table",
        "presentation": "structured_modal",
        "animation_profile": "low_confidence" if not ok else "result",
        "ok": ok,
        "title": "Rachunki i koszty",
        "subject": "rachunki",
        "summary": _compact(answer, 360),
        "message": _compact(answer, 360),
        "structured_data": {
            "title": "Rachunki",
            "columns": ["Pozycja", "Kwota", "Termin"],
            "rows": public_rows,
            "total": total,
            "currency": detected_currency or "PLN",
            "notes": _compact(answer, 360),
        },
        "sources": ["JARVIS answer"],
        "cost": {"operation": "visual_planner", "estimated_cost_usd": 0.0},
        "query": question,
    }


def _extract_structured_rows(answer: str) -> tuple[list[dict[str, Any]], str | None]:
    rows: list[dict[str, Any]] = []
    detected_currency: str | None = None
    for line in re.split(r"[\n;]+", answer or ""):
        clean_line = re.sub(r"^\s*[-*•\d.)]+\s*", "", line).strip()
        if not clean_line:
            continue
        if any(label in _normalize(clean_line) for label in ("razem", "suma", "lacznie", "total")):
            continue
        match = AMOUNT_WITH_CURRENCY_RE.search(clean_line)
        if not match:
            continue
        amount = _parse_amount(match.group("amount"))
        currency = _normalize_currency(match.group("currency"))
        detected_currency = detected_currency or currency
        item = clean_line[: match.start()].strip(" :-") or f"Pozycja {len(rows) + 1}"
        rows.append(
            {
                "item": _compact(item, 90),
                "amount": _format_amount(amount, currency),
                "numeric_amount": amount,
                "due": _extract_due_date(clean_line),
            }
        )
    return rows[:12], detected_currency


def _extract_total(answer: str) -> float | None:
    for line in re.split(r"[\n;]+", answer or ""):
        normalized = _normalize(line)
        if not any(label in normalized for label in ("razem", "suma", "lacznie", "total")):
            continue
        match = AMOUNT_WITH_CURRENCY_RE.search(line)
        if match:
            return _parse_amount(match.group("amount"))
    return None


def _extract_due_date(text: str) -> str:
    match = DUE_DATE_RE.search(text or "")
    return match.group("due") if match else ""


def _parse_amount(value: str) -> float:
    normalized = (value or "0").replace(" ", "")
    if "," in normalized and "." in normalized:
        normalized = normalized.replace(".", "").replace(",", ".")
    elif "," in normalized:
        normalized = normalized.replace(",", ".")
    elif normalized.count(".") == 1 and len(normalized.rsplit(".", 1)[1]) == 3:
        normalized = normalized.replace(".", "")
    try:
        return float(normalized)
    except ValueError:
        return 0.0


def _format_amount(value: float, currency: str) -> str:
    display = str(int(value)) if float(value).is_integer() else f"{value:.2f}"
    return f"{display} {currency}"


def _normalize_currency(value: str) -> str:
    normalized = _normalize(value)
    if normalized in {"zl", "pln"}:
        return "PLN"
    return normalized.upper() or "PLN"


def _filter_search_results(web_results: WebSearchBundle, subject: str) -> WebSearchBundle:
    filtered = [
        result
        for result in web_results.results
        if _subject_in_text(subject, f"{result.title} {result.snippet} {result.url}")
    ]
    return WebSearchBundle(query=web_results.query, results=filtered, source=web_results.source)


def _looks_factual(question: str, answer: str) -> bool:
    normalized = _normalize(question)
    if any(hint in normalized for hint in FACTUAL_QUESTION_HINTS):
        return True
    if "?" in question and _extract_subject_from_answer(answer):
        return True
    return False


def _extract_subject_from_question(question: str) -> str | None:
    cleaned = _strip_wake_words(question)
    patterns = (
        r"^(?:kim|kto)\s+(?:jest|byl|byla)\s+(.+)$",
        r"^(?:co|czym)\s+(?:jest|sa)\s+(.+)$",
        r"^(?:opowiedz|powiedz)\s+(?:mi\s+)?(?:o|o tym kim jest)\s+(.+)$",
    )
    for pattern in patterns:
        match = re.search(pattern, cleaned, flags=re.IGNORECASE)
        if match:
            return _clean_subject(match.group(1))
    return None


def _extract_subject_from_answer(answer: str) -> str | None:
    candidates = _extract_subject_candidates_from_answer(answer)
    return candidates[0]["subject"] if candidates else None


def _extract_subject_candidates_from_answer(answer: str) -> list[dict[str, Any]]:
    words = re.findall(r"[^\W\d_][\w'-]*", answer or "", flags=re.UNICODE)
    candidates: dict[str, dict[str, Any]] = {}
    for index, word in enumerate(words):
        if not word[:1].isupper():
            continue
        candidate_words = [word]
        for next_word in words[index + 1 : index + 4]:
            if not next_word[:1].isupper():
                break
            candidate_words.append(next_word)
        candidate = _clean_subject(" ".join(candidate_words))
        if not candidate or candidate.lower() in STOP_SUBJECT_WORDS:
            continue
        if len(candidate.split()) == 1 and _normalize(candidate) in STOP_SUBJECT_WORDS:
            continue
        if not _looks_like_named_entity(candidate):
            continue
        score = _score_subject_candidate(candidate, index)
        key = _normalize(candidate)
        if key not in candidates or score > candidates[key]["score"]:
            candidates[key] = {
                "subject": candidate,
                "score": score,
                "confidence": min(0.95, 0.58 + score / 10),
            }

    ranked = sorted(
        candidates.values(),
        key=lambda candidate: (candidate["score"], len(candidate["subject"])),
        reverse=True,
    )
    return [
        {
            "subject": candidate["subject"],
            "confidence": round(float(candidate["confidence"]), 2),
        }
        for candidate in ranked
    ]


def _score_subject_candidate(candidate: str, index: int) -> float:
    words = candidate.split()
    score = float(len(words) * 2)
    if len(words) >= 2:
        score += 3
    if len(words) == 1:
        score -= 4
    if index <= 6:
        score += 1
    if words and words[0].lower() in SUBJECT_LEADING_WORDS:
        score -= 4
    return score


def _looks_like_named_entity(text: str) -> bool:
    words = (text or "").split()
    if not words:
        return False
    if len(words) == 1 and _normalize(words[0]) in STOP_SUBJECT_WORDS:
        return False
    return all(word[:1].isupper() for word in words[:2])


def _profile_matches_subject(profile: EntityProfile, subject: str) -> bool:
    if not profile or profile.ok is False:
        return False
    evidence = f"{profile.title} {profile.summary}"
    return _subject_in_text(subject, evidence)


def _subject_in_text(subject: str, text: str) -> bool:
    normalized_subject = _normalize(subject)
    normalized_text = _normalize(text)
    if not normalized_subject or not normalized_text:
        return False
    if normalized_subject in normalized_text:
        return True
    tokens = [token for token in normalized_subject.split() if len(token) > 2]
    return bool(tokens) and all(token in normalized_text for token in tokens)


def _strip_wake_words(text: str) -> str:
    text = re.sub(r"\bjarvis\b", "", text, flags=re.IGNORECASE)
    text = re.sub(r"\bspisz\b|\bszpisz\b|\bśpisz\b", "", text, flags=re.IGNORECASE)
    return re.sub(r"\s+", " ", text).strip(" ?!.,;:")


def _clean_subject(subject: str) -> str | None:
    cleaned = re.sub(r"[?!.,;:]+$", "", subject or "").strip()
    cleaned = re.sub(
        r"\b(aktualnie|teraz|dzisiaj|na swiecie|na świecie|prosze|szefie)\b",
        "",
        cleaned,
        flags=re.IGNORECASE,
    )
    cleaned = re.sub(r"\s+", " ", cleaned).strip()
    if not cleaned:
        return None
    words = [word for word in cleaned.split() if word.lower() not in STOP_SUBJECT_WORDS]
    while words and _normalize(words[0]) in SUBJECT_LEADING_WORDS:
        words.pop(0)
    if not words:
        return None
    return " ".join(words[:5]).strip()


def _is_uncertain_answer(answer: str) -> bool:
    normalized = _normalize(answer)
    return any(hint in normalized for hint in UNCERTAIN_ANSWER_HINTS)


def _normalize(text: str) -> str:
    lowered = unicodedata.normalize("NFKD", (text or "").lower())
    lowered = "".join(character for character in lowered if not unicodedata.combining(character))
    replacements = {
        "ą": "a",
        "ć": "c",
        "ę": "e",
        "ł": "l",
        "ń": "n",
        "ó": "o",
        "ś": "s",
        "ż": "z",
        "ź": "z",
    }
    for source, target in replacements.items():
        lowered = lowered.replace(source, target)
    lowered = re.sub(r"[^a-z0-9 ]+", " ", lowered)
    return re.sub(r"\s+", " ", lowered).strip()


def _search_wikipedia_title(subject: str, timeout: float) -> str | None:
    params = urllib.parse.urlencode(
        {
            "action": "query",
            "list": "search",
            "srsearch": subject,
            "srlimit": 1,
            "format": "json",
            "utf8": 1,
        }
    )
    data = _fetch_json(f"{WIKIPEDIA_SEARCH_URL}?{params}", timeout=timeout)
    results = ((data.get("query") or {}).get("search") or [])
    if not results:
        return None
    return str(results[0].get("title") or "").strip() or None


def _fetch_wikipedia_summary(title: str, timeout: float) -> dict[str, Any]:
    quoted = urllib.parse.quote(title.replace(" ", "_"))
    return _fetch_json(f"{WIKIPEDIA_SUMMARY_URL}/{quoted}", timeout=timeout)


def _fetch_json(url: str, timeout: float) -> dict[str, Any]:
    request = urllib.request.Request(url, headers={"User-Agent": "JARVIS-local-ui/1.0"})
    with urllib.request.urlopen(request, timeout=timeout) as response:
        return json.loads(response.read().decode("utf-8"))


def _extract_facts(text: str) -> list[str]:
    parts = re.split(r"(?<=[.!?])\s+", (text or "").strip())
    facts = []
    for part in parts:
        compact = _compact(part, 140)
        if len(compact) >= 16:
            facts.append(compact)
        if len(facts) >= 5:
            break
    return facts


def _compact(text: str, limit: int) -> str:
    cleaned = re.sub(r"\s+", " ", text or "").strip()
    if len(cleaned) <= limit:
        return cleaned
    return cleaned[: max(0, limit - 1)].rstrip() + "..."
