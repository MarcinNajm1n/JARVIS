from dataclasses import replace

from src.config import load_settings
from src.episodic_memory import EpisodicMemoryStore


def test_episodic_memory_przechowuje_ostatni_kontekst(tmp_path):
    settings = replace(load_settings(), episodic_memory_path=tmp_path / "episodic.json")
    memory = EpisodicMemoryStore(settings)

    memory.remember_event("user", "Pierwsze pytanie")
    memory.remember_event("assistant", "Pierwsza odpowiedz")

    snapshot = EpisodicMemoryStore(settings).snapshot()
    assert snapshot["events_count"] == 2
    assert "Pierwsze pytanie" in snapshot["recent_context"]
