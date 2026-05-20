from __future__ import annotations

from dataclasses import dataclass

from src.assistant_state import AssistantStateStore
from src.cost_tracker import CostTracker
from src.episodic_memory import EpisodicMemoryStore
from src.project_store import ProjectStore
from src.task_store import TaskStore


@dataclass
class OperationalBriefing:
    active_project: str
    open_tasks: int
    recent_context: str
    next_step: str
    estimated_cost_usd: float

    def format(self) -> str:
        return (
            f"Dzien dobry. Projekt: {self.active_project}. "
            f"Otwarte zadania: {self.open_tasks}. "
            f"Koszt sesji LLM od pomiaru: ${self.estimated_cost_usd:.6f}. "
            f"Rekomendowany krok: {self.next_step}"
        )


def build_operational_briefing(
    assistant_state: AssistantStateStore,
    task_store: TaskStore,
    project_store: ProjectStore,
    episodic_memory: EpisodicMemoryStore,
    cost_tracker: CostTracker,
) -> OperationalBriefing:
    active_project = assistant_state.get_active_project() or "brak aktywnego projektu"
    open_tasks = len(task_store.list(include_done=False))
    project_status = project_store.summarize(assistant_state.get_active_project())
    recent_context = episodic_memory.recent_context(limit=3)
    next_step = _choose_next_step(project_status, open_tasks, recent_context)
    cost = cost_tracker.snapshot()["estimated_cost_usd"]
    return OperationalBriefing(
        active_project=active_project,
        open_tasks=open_tasks,
        recent_context=recent_context,
        next_step=next_step,
        estimated_cost_usd=cost,
    )


def _choose_next_step(project_status: str, open_tasks: int, recent_context: str) -> str:
    combined = f"{project_status}\n{recent_context}".lower()
    if "wake" in combined or "stt" in combined or "mikrofon" in combined:
        return "sprawdzic stabilnosc aktywacji glosowej i STT."
    if open_tasks:
        return "wybrac jedno otwarte zadanie i doprowadzic je do testow."
    return "ustalic kolejny cel operacyjny projektu."
