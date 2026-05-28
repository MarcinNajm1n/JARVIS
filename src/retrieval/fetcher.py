from __future__ import annotations

import re
from typing import Any

import httpx

from src.retrieval.evidence import score_source
from src.retrieval.models import FetchedSource, QueryPlan, SearchResult


USER_AGENT = "JarvisBot/1.0"


class PageFetcher:
    def __init__(self, timeout_seconds: float = 20.0, max_chars: int = 20_000) -> None:
        self.timeout_seconds = timeout_seconds
        self.max_chars = max_chars

    def fetch_many(self, results: list[SearchResult], plan: QueryPlan) -> list[FetchedSource]:
        return [self.fetch(result, plan) for result in results]

    def fetch(self, result: SearchResult, plan: QueryPlan) -> FetchedSource:
        try:
            html = self._download(result.url)
            extracted = extract_text(html, result.url)
            if not extracted.strip():
                return _fetched_error(result, plan, "extraction failed")
            return FetchedSource(
                title=result.title,
                url=result.url,
                provider=result.provider,
                raw_snippet=result.snippet,
                extracted_text=_compact(extracted, self.max_chars),
                published_at=result.published_at,
                trust_score=score_source(result.url, plan.mode, plan.original_question),
            )
        except Exception as error:
            return _fetched_error(result, plan, f"fetch failed: {error}")

    def _download(self, url: str) -> str:
        headers = {"User-Agent": USER_AGENT}
        with httpx.Client(timeout=self.timeout_seconds, follow_redirects=True, headers=headers) as client:
            response = client.get(url)
            response.raise_for_status()
            return response.text


def extract_text(html: str, url: str = "") -> str:
    extracted = _extract_with_trafilatura(html, url)
    if extracted:
        return extracted
    extracted = _extract_with_bs4(html)
    if extracted:
        return extracted
    return _extract_with_regex(html)


def _extract_with_trafilatura(html: str, url: str) -> str:
    try:
        import trafilatura

        return trafilatura.extract(
            html,
            url=url or None,
            include_comments=False,
            include_tables=False,
            favor_precision=True,
        ) or ""
    except Exception:
        return ""


def _extract_with_bs4(html: str) -> str:
    try:
        from bs4 import BeautifulSoup

        soup = BeautifulSoup(html, "html.parser")
        for tag in soup(["script", "style", "noscript", "svg"]):
            tag.decompose()
        return re.sub(r"\s+", " ", soup.get_text(" ")).strip()
    except Exception:
        return ""


def _extract_with_regex(html: str) -> str:
    cleaned = re.sub(r"<(script|style).*?</\1>", " ", html or "", flags=re.IGNORECASE | re.DOTALL)
    cleaned = re.sub(r"<[^>]+>", " ", cleaned)
    return re.sub(r"\s+", " ", cleaned).strip()


def _fetched_error(result: SearchResult, plan: QueryPlan, error: str) -> FetchedSource:
    fallback_text = result.snippet or ""
    return FetchedSource(
        title=result.title,
        url=result.url,
        provider=result.provider,
        raw_snippet=result.snippet,
        extracted_text=fallback_text,
        published_at=result.published_at,
        trust_score=score_source(result.url, plan.mode, plan.original_question),
        fetch_error=error if not fallback_text else None,
    )


def _compact(text: str, limit: int) -> str:
    cleaned = re.sub(r"\s+", " ", text or "").strip()
    if len(cleaned) <= limit:
        return cleaned
    return cleaned[: max(0, limit - 1)].rstrip() + "..."
