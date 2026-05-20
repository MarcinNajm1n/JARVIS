from dataclasses import replace

from src.assistant_state import AssistantStateStore
from src.config import load_settings
from src.cost_tracker import CostTracker
from src.episodic_memory import EpisodicMemoryStore
from src.operational_briefing import build_operational_briefing
from src.project_store import ProjectStore
from src.task_store import TaskStore


def test_operational_briefing_laczy_projekt_zadania_pamiec_i_koszt(tmp_path):
    settings = replace(
        load_settings(),
        assistant_state_path=tmp_path / "assistant_state.json",
        task_store_path=tmp_path / "tasks.json",
        project_store_path=tmp_path / "projects.json",
        episodic_memory_path=tmp_path / "episodic_memory.json",
        cost_log_path=tmp_path / "usage_costs.json",
    )
    assistant_state = AssistantStateStore(settings)
    assistant_state.set_active_project("JARVIS")
    task_store = TaskStore(settings)
    task_store.add("Usprawnic STT")
    project_store = ProjectStore(settings)
    project_store.add_note("JARVIS", "Stabilizujemy wake flow.")
    episodic_memory = EpisodicMemoryStore(settings)
    episodic_memory.remember_event("user", "testujemy mikrofon")
    cost_tracker = CostTracker(settings)
    cost_tracker.record_llm_usage("gpt-4.1-mini", 100, 50, "test")

    briefing = build_operational_briefing(
        assistant_state,
        task_store,
        project_store,
        episodic_memory,
        cost_tracker,
    )

    assert briefing.active_project == "JARVIS"
    assert briefing.open_tasks == 1
    assert "aktywacji glosowej" in briefing.next_step
    assert "Koszt sesji" in briefing.format()
