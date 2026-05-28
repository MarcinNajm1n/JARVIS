from __future__ import annotations

import re
from urllib.parse import urlparse

from src.retrieval.models import EvidenceChunk, FetchedSource, SearchMode
from src.retrieval.reranker import Reranker


OFFICIAL_HINTS = (".gov", "gov.pl", "europa.eu", "who.int", "ec.europa.eu")
EDU_HINTS = (".edu", "edu.pl")
SOFTWARE_HINTS = ("github.com", "pypi.org", "npmjs.com", "readthedocs.io", "fastapi.tiangolo.com")
NEWS_HINTS = ("reuters.com", "apnews.com", "bbc.com", "bloomberg.com", "forbes.com", "ft.com")
SEO_BAD_HINTS = ("coupon", "casino", "clickbait", "promo-code", "affiliate", "best-", "top10")


class EvidenceBuilder:
    def __init__(self, reranker: Reranker | None = None, top_k: int = 5) -> None:
        self.reranker = reranker or Reranker()
        self.top_k = top_k

    def build(self, question: str, sources: list[FetchedSource], top_k: int | None = None) -> list[EvidenceChunk]:
        chunks: list[EvidenceChunk] = []
        for source in sources:
            if source.fetch_error or not source.extracted_text.strip():
                continue
            for text in split_chunks(source.extracted_text):
                chunks.append(
                    EvidenceChunk(
                        source_url=source.url,
                        source_title=source.title,
                        text=text,
                        relevance_score=0.0,
                        trust_score=source.trust_score,
                    )
                )
        if not chunks:
            return []
        return self.reranker.rank(question, chunks, top_k=top_k or self.top_k)


def split_chunks(text: str, min_chars: int = 40, max_chars: int = 900) -> list[str]:
    paragraphs = [part.strip() for part in re.split(r"\n{2,}|\r\n{2,}", text or "") if part.strip()]
    if not paragraphs:
        paragraphs = [part.strip() for part in re.split(r"(?<=[.!?])\s+", text or "") if part.strip()]

    chunks = []
    current = ""
    for paragraph in paragraphs:
        if len(current) + len(paragraph) + 1 <= max_chars:
            current = f"{current} {paragraph}".strip()
            continue
        if len(current) >= min_chars:
            chunks.append(_compact(current, max_chars))
        current = paragraph
    if len(current) >= min_chars:
        chunks.append(_compact(current, max_chars))
    return chunks


def score_source(url: str, mode: str | SearchMode, question: str = "") -> float:
    domain = urlparse(url).netloc.lower().removeprefix("www.")
    evidence = f"{domain} {url}".lower()
    points = 0
    if any(hint in evidence for hint in OFFICIAL_HINTS):
        points += 4
    if any(hint in evidence for hint in EDU_HINTS):
        points += 3
    if mode == SearchMode.SOFTWARE.value and any(hint in evidence for hint in SOFTWARE_HINTS):
        points += 3
    if any(hint in evidence for hint in NEWS_HINTS):
        points += 2
    if _domain_matches_question(domain, question):
        points += 5
    if any(hint in evidence for hint in SEO_BAD_HINTS):
        points -= 2
    if "casino" in evidence or "clickbait" in evidence:
        points -= 5
    return max(0.05, min(1.0, 0.45 + points / 12))


def _domain_matches_question(domain: str, question: str) -> bool:
    normalized_question = _normalize(question)
    if not normalized_question or not domain:
        return False
    domain_root = domain.split(".")[0]
    return len(domain_root) > 3 and domain_root in normalized_question


def _normalize(text: str) -> str:
    lowered = (text or "").lower()
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
    return re.sub(r"[^a-z0-9 ]+", " ", lowered)


def _compact(text: str, limit: int) -> str:
    cleaned = re.sub(r"\s+", " ", text or "").strip()
    if len(cleaned) <= limit:
        return cleaned
    return cleaned[: max(0, limit - 1)].rstrip() + "..."
