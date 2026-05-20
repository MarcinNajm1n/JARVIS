from dataclasses import replace
from types import SimpleNamespace

from src.config import load_settings
from src.conversation_engine import ConversationEngine
from src.task_store import TaskStore


def test_naturalne_polecenie_model_wybiera_funkcje_i_store_sie_zmienia(tmp_path):
    settings = replace(
        load_settings(),
        history_path=tmp_path / "conversation_history.json",
        long_term_memory_path=tmp_path / "long_term_memory.json",
        user_profile_path=tmp_path / "user_profile.json",
        task_store_path=tmp_path / "tasks.json",
        project_store_path=tmp_path / "projects.json",
        assistant_state_path=tmp_path / "assistant_state.json",
        tool_call_log_path=tmp_path / "tool_calls.json",
        conversation_summary_path=tmp_path / "conversation_summary.json",
        episodic_memory_path=tmp_path / "episodic_memory.json",
        cost_log_path=tmp_path / "usage_costs.json",
        feedback_path=tmp_path / "feedback.json",
        tts_enabled=False,
        auto_memory_enabled=False,
        rag_enabled=False,
    )
    engine = ConversationEngine(settings)
    engine.llm_client._client = _FakeOpenAIClient()

    response = engine.generate_response(
        "Dodaj zadanie, zeby sprawdzic function calling.",
        speak=False,
    )

    tasks = TaskStore(settings).list()
    assert response == "Dodalem zadanie do listy."
    assert tasks[0]["title"] == "Sprawdzic function calling"
    assert settings.tool_call_log_path.exists()


class _FakeOpenAIClient:
    def __init__(self):
        self.responses = _FakeResponses()


class _FakeResponses:
    def __init__(self):
        self.calls = 0

    def create(self, **_kwargs):
        self.calls += 1
        if self.calls == 1:
            return SimpleNamespace(
                output=[
                    SimpleNamespace(
                        type="function_call",
                        call_id="call_add_task",
                        name="add_task",
                        arguments='{"title": "Sprawdzic function calling"}',
                    )
                ],
                output_text="",
            )
        return SimpleNamespace(output=[], output_text="Dodalem zadanie do listy.")
