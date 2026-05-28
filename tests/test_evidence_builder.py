from src.retrieval.evidence import EvidenceBuilder
from src.retrieval.models import EvidenceChunk, FetchedSource


class FakeReranker:
    def rank(self, question, chunks, top_k=5):
        ranked = []
        for index, chunk in enumerate(chunks):
            ranked.append(chunk.model_copy(update={"relevance_score": 1.0 - index * 0.1}))
        return ranked[:top_k]


def test_evidence_builder_tworzy_chunki_i_top_k():
    source = FetchedSource(
        title="FastAPI release",
        url="https://github.com/fastapi/fastapi/releases",
        provider="test",
        extracted_text=(
            "FastAPI ma nowe wydanie z poprawkami. " * 8
            + "\n\n"
            + "Release notes opisuja najwazniejsze zmiany. " * 8
        ),
        trust_score=0.9,
    )

    evidence = EvidenceBuilder(reranker=FakeReranker(), top_k=1).build("FastAPI release", [source])

    assert len(evidence) == 1
    assert isinstance(evidence[0], EvidenceChunk)
    assert evidence[0].source_url == source.url
    assert evidence[0].source_title == source.title
