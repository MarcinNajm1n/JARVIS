import json
from pathlib import Path

from src.function_tools import (
    JARVIS_FUNCTION_TOOLS,
    JARVIS_TOOL_RISK,
    RISK_REQUIRES_CONFIRMATION,
    JarvisToolContext,
    execute_jarvis_tool,
)
from src.long_term_memory import wczytaj_pamiec_stala
from src.weather_service import WeatherResult


def test_function_tools_definiuja_narzedzie_add_task_w_formacie_responses_api():
    add_task = next(tool for tool in JARVIS_FUNCTION_TOOLS if tool["name"] == "add_task")

    assert add_task["type"] == "function"
    assert add_task["strict"] is True
    assert add_task["parameters"]["required"] == ["title"]
    assert add_task["parameters"]["additionalProperties"] is False


def test_execute_jarvis_tool_add_task_dodaje_zadanie_do_store():
    context = _build_context()

    raw_result = execute_jarvis_tool(
        "add_task",
        {"title": "Sprawdzic kompatybilnosc function calling"},
        context,
    )
    result = json.loads(raw_result)

    assert result["ok"] is True
    assert result["result"]["task"]["id"] == 1
    assert context.task_store.tasks[0]["title"] == "Sprawdzic kompatybilnosc function calling"


def test_execute_jarvis_tool_add_project_note_zwraca_blad_gdy_brak_aktywnego_projektu():
    context = _build_context()

    raw_result = execute_jarvis_tool(
        "add_project_note",
        {"note": "Ta notatka nie ma jeszcze projektu."},
        context,
    )
    result = json.loads(raw_result)

    assert result["ok"] is False
    assert result["tool"] == "add_project_note"
    assert "Brak aktywnego projektu" in result["error"]


def test_execute_jarvis_tool_add_memory_fact_zapisuje_pamiec_stala(tmp_path: Path):
    context = _build_context(long_term_memory_path=tmp_path / "long_term_memory.json")

    raw_result = execute_jarvis_tool(
        "add_memory_fact",
        {
            "fact": "Uzytkownik rozwija projekt JARVIS w Pythonie.",
            "memory_type": "projects",
        },
        context,
    )
    result = json.loads(raw_result)

    assert result["ok"] is True
    assert result["result"]["added"] is True
    assert wczytaj_pamiec_stala(context.long_term_memory_path) == [
        result["result"]["entry"]
    ]


def test_execute_jarvis_tool_search_commands_znajduje_wylaczenie_programu():
    context = _build_context()

    raw_result = execute_jarvis_tool(
        "search_commands",
        {"query": "jak moge cie wylaczyc"},
        context,
    )
    result = json.loads(raw_result)

    assert result["ok"] is True
    assert result["result"]["commands"][0]["command"] == "jarvis wylacz sie"


def test_function_tools_definiuja_get_weather():
    weather_tool = next(tool for tool in JARVIS_FUNCTION_TOOLS if tool["name"] == "get_weather")

    assert weather_tool["type"] == "function"
    assert weather_tool["strict"] is True
    assert weather_tool["parameters"]["required"] == ["location"]
    assert JARVIS_TOOL_RISK["get_weather"] == "safe"


def test_execute_jarvis_tool_get_weather_zwraca_payload_wizualny(monkeypatch):
    context = _build_context()

    def fake_weather(location):
        return WeatherResult(
            ok=True,
            location=location,
            lat=52.52,
            lon=13.405,
            temperature=18,
            description="pochmurno",
            wind=12,
            humidity=60,
            cloud_cover=75,
            observed_at="2026-05-20T12:00",
        )

    monkeypatch.setattr("src.function_tools.get_current_weather", fake_weather)
    raw_result = execute_jarvis_tool("get_weather", {"location": "Berlin"}, context)
    result = json.loads(raw_result)

    assert result["ok"] is True
    assert result["result"]["mode"] == "map_weather"
    assert result["result"]["location"] == "Berlin"
    assert result["result"]["weather"]["temperature"] == 18


def test_tool_risk_klasyfikuje_remove_task_jako_wymagajace_potwierdzenia():
    assert JARVIS_TOOL_RISK["remove_task"] == RISK_REQUIRES_CONFIRMATION


def test_execute_jarvis_tool_remove_task_wymaga_potwierdzenia():
    context = _build_context()
    context.task_store.add("Testowe zadanie")

    raw_result = execute_jarvis_tool(
        "remove_task",
        {"task_id": 1, "confirmation": ""},
        context,
    )
    result = json.loads(raw_result)

    assert result["ok"] is False
    assert result["confirmation_required"] is True
    assert len(context.task_store.tasks) == 1


def test_execute_jarvis_tool_remove_task_po_potwierdzeniu_usuwa_zadanie():
    context = _build_context()
    context.task_store.add("Testowe zadanie")

    raw_result = execute_jarvis_tool(
        "remove_task",
        {"task_id": 1, "confirmation": "potwierdzam"},
        context,
    )
    result = json.loads(raw_result)

    assert result["ok"] is True
    assert context.task_store.tasks == []


def test_execute_jarvis_tool_mark_task_done_zmienia_store():
    context = _build_context()
    context.task_store.add("Testowe zadanie")

    raw_result = execute_jarvis_tool("mark_task_done", {"task_id": 1}, context)
    result = json.loads(raw_result)

    assert result["ok"] is True
    assert context.task_store.tasks[0]["done"] is True


def test_execute_jarvis_tool_search_memory_znajduje_wpis():
    context = _build_context()
    execute_jarvis_tool(
        "add_memory_fact",
        {"fact": "Kornel preferuje krotkie odpowiedzi.", "memory_type": "preferences"},
        context,
    )

    raw_result = execute_jarvis_tool(
        "search_memory",
        {"query": "krotkie odpowiedzi"},
        context,
    )
    result = json.loads(raw_result)

    assert result["ok"] is True
    assert result["result"]["matches"][0]["type"] == "preferences"


def test_execute_jarvis_tool_loguje_wywolanie(tmp_path: Path):
    context = _build_context(tool_call_log_path=tmp_path / "tool_calls.json")

    execute_jarvis_tool("add_task", {"title": "Logowane zadanie"}, context)
    log_entries = json.loads(context.tool_call_log_path.read_text(encoding="utf-8"))

    assert log_entries[0]["tool"] == "add_task"
    assert log_entries[0]["risk"] == "safe"
    assert log_entries[0]["status"] == "ok"


def _build_context(
    long_term_memory_path: Path | None = None,
    tool_call_log_path: Path | None = None,
) -> JarvisToolContext:
    return JarvisToolContext(
        assistant_state=_FakeAssistantState(),
        profile_store=_FakeProfileStore(),
        task_store=_FakeTaskStore(),
        project_store=_FakeProjectStore(),
        long_term_memory=[],
        long_term_memory_path=long_term_memory_path,
        tool_call_log_path=tool_call_log_path,
    )


class _FakeTaskStore:
    def __init__(self):
        self.tasks = []

    def add(self, title):
        task = {"id": len(self.tasks) + 1, "title": title, "done": False}
        self.tasks.append(task)
        return task

    def list(self, include_done=True):
        if include_done:
            return list(self.tasks)
        return [task for task in self.tasks if not task["done"]]

    def mark_done(self, task_id):
        for task in self.tasks:
            if task["id"] == task_id:
                task["done"] = True
                return True
        return False

    def remove(self, task_id):
        before = len(self.tasks)
        self.tasks = [task for task in self.tasks if task["id"] != task_id]
        return len(self.tasks) != before


class _FakeProfileStore:
    def __init__(self):
        self.values = {}

    def set_value(self, key, value):
        self.values[key] = value

    def get(self):
        return dict(self.values)


class _FakeAssistantState:
    def __init__(self):
        self.active_project = None
        self.response_mode = "jarvis"

    def get_active_project(self):
        return self.active_project

    def set_active_project(self, project_name):
        self.active_project = project_name

    def set_response_mode(self, mode):
        self.response_mode = mode


class _FakeProjectStore:
    def __init__(self):
        self.projects = {}
        self.notes = []

    def ensure_project(self, name):
        self.projects[name] = {"name": name}
        return self.projects[name]

    def add_note(self, project_name, note):
        self.notes.append({"project_name": project_name, "note": note})

    def summarize(self, project_name):
        return f"Aktywny projekt: {project_name or 'brak'}"
