from dataclasses import replace
from types import SimpleNamespace

from src.config import load_settings
from src.conversation_engine import ConversationEngine


def test_history_disabled_nie_zapisuje_conversation_history(tmp_path):
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
        feedback_path=tmp_path / "feedback.json",
        tts_enabled=False,
        auto_memory_enabled=False,
        rag_enabled=False,
        history_enabled=False,
    )
    engine = ConversationEngine(settings)
    engine.llm_client._client = _FakeOpenAIClient()

    response = engine.generate_response("Test prywatnosci.", speak=False)

    assert response == "Odpowiedz testowa."
    assert not settings.history_path.exists()


class _FakeOpenAIClient:
    def __init__(self):
        self.responses = _FakeResponses()


class _FakeResponses:
    def create(self, **_kwargs):
        return SimpleNamespace(output=[], output_text="Odpowiedz testowa.")
