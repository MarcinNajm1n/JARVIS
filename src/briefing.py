from __future__ import annotations

from datetime import datetime

from src.project_store import ProjectStore
from src.task_store import TaskStore
from src.profile_store import UserProfileStore


def build_briefing(
    profile_store: UserProfileStore,
    task_store: TaskStore,
    project_store: ProjectStore,
    active_project: str | None,
    memory_count: int,
) -> str:
    profile = profile_store.get()
    open_tasks = task_store.list(include_done=False)
    project_summary = project_store.summarize(active_project)
    current_time = datetime.now().strftime("%Y-%m-%d %H:%M")

    lines = [
        f"Briefing operacyjny - {current_time}",
        f"Uzytkownik: {profile.get('name', 'nieznany')}",
        f"Profil: {profile.get('field', 'brak danych')}",
        project_summary,
        f"Pamiec stala: {memory_count} wpisow",
        f"Otwarte zadania: {len(open_tasks)}",
    ]

    if open_tasks:
        lines.append("Najblizsze zadania:")
        lines.extend(f"- #{task['id']} {task['title']}" for task in open_tasks[:5])

    lines.append("Sugerowany nastepny krok: wybierz jedno zadanie i popros o plan wykonania.")
    return "\n".join(lines)
