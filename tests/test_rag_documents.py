from dataclasses import replace

from src.config import load_settings
from src.rag import RAGMemory


def test_rag_przeczytaj_dokument_zwraca_wlasciwe_zrodlo(tmp_path):
    document = tmp_path / "decyzje.md"
    document.write_text(
        "# Decyzje\n- Uzywamy wake gate.\n- Nie wysylamy tekstu do LLM bez aktywacji.",
        encoding="utf-8",
    )
    settings = replace(
        load_settings(),
        documents_dir=tmp_path,
        vector_store_dir=tmp_path / "vector_store",
        rag_enabled=True,
    )

    context = RAGMemory(settings).retrieve_context(
        "Jarvis, przeczytaj dokument decyzje.md i stresc decyzje"
    )

    assert "Zrodlo: decyzje.md" in context
    assert "wake gate" in context
