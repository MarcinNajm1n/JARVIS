from __future__ import annotations

import math
import re
from typing import Any

from src.retrieval.models import EvidenceChunk


class Reranker:
    def __init__(self, model_name: str = "sentence-transformers/all-MiniLM-L6-v2") -> None:
        self.model_name = model_name
        self._model: Any | None = None
        self._model_failed = False

    def rank(self, question: str, chunks: list[EvidenceChunk], top_k: int = 5) -> list[EvidenceChunk]:
        if not chunks:
            return []
        scores = self._semantic_scores(question, chunks)
        if scores is None:
            scores = [_keyword_score(question, chunk.text) for chunk in chunks]

        ranked = []
        for chunk, score in zip(chunks, scores, strict=False):
            combined = (float(score) * 0.72) + (chunk.trust_score * 0.28)
            ranked.append(
                chunk.model_copy(update={"relevance_score": round(max(0.0, min(1.0, combined)), 3)})
            )
        ranked.sort(key=lambda item: (item.relevance_score, item.trust_score), reverse=True)
        return ranked[:top_k]

    def _semantic_scores(self, question: str, chunks: list[EvidenceChunk]) -> list[float] | None:
        if self._model_failed:
            return None
        try:
            model = self._load_model()
            embeddings = model.encode([question, *[chunk.text for chunk in chunks]], normalize_embeddings=True)
            query_embedding = embeddings[0]
            return [_cosine(query_embedding, embedding) for embedding in embeddings[1:]]
        except Exception:
            self._model_failed = True
            return None

    def _load_model(self) -> Any:
        if self._model is None:
            from sentence_transformers import SentenceTransformer

            self._model = SentenceTransformer(self.model_name)
        return self._model


def _keyword_score(question: str, text: str) -> float:
    question_tokens = set(_tokens(question))
    text_tokens = set(_tokens(text))
    if not question_tokens or not text_tokens:
        return 0.0
    overlap = len(question_tokens & text_tokens) / len(question_tokens)
    phrase_bonus = 0.15 if " ".join(list(question_tokens)[:2]) in " ".join(text_tokens) else 0.0
    return max(0.05, min(1.0, overlap + phrase_bonus))


def _tokens(text: str) -> list[str]:
    normalized = (text or "").lower()
    normalized = (
        normalized.replace("\u0105", "a")
        .replace("\u0107", "c")
        .replace("\u0119", "e")
        .replace("\u0142", "l")
        .replace("\u0144", "n")
        .replace("\u00f3", "o")
        .replace("\u015b", "s")
        .replace("\u017c", "z")
        .replace("\u017a", "z")
    )
    stop = {"jest", "jaka", "jaki", "jakie", "kto", "co", "sie", "the", "and", "oraz", "dla"}
    return [token for token in re.findall(r"[a-z0-9]+", normalized) if len(token) > 2 and token not in stop]


def _cosine(left: Any, right: Any) -> float:
    dot = sum(float(a) * float(b) for a, b in zip(left, right, strict=False))
    left_norm = math.sqrt(sum(float(a) * float(a) for a in left))
    right_norm = math.sqrt(sum(float(b) * float(b) for b in right))
    if not left_norm or not right_norm:
        return 0.0
    return max(0.0, min(1.0, (dot / (left_norm * right_norm) + 1) / 2))
