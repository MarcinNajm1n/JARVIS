from dataclasses import replace

from src.config import load_settings
from src.conversation_engine import ConversationEngine


def test_listen_for_command_zwraca_poprawiona_transkrypcje_przed_llm(tmp_path):
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
        transcript_correction_enabled=True,
        transcript_correction_with_llm=False,
    )
    engine = ConversationEngine(settings)
    engine.stt_client.listen_and_transcribe = lambda max_seconds=None: (
        "dżarwis spisz sprawdz fast api"
    )

    text, _utterance_end_time = engine.listen_for_command()

    assert text == "jarvis śpisz? sprawdz FastAPI"


def test_listen_once_pomija_korekte_gdy_jest_wylaczona(tmp_path):
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
        transcript_correction_enabled=False,
    )
    engine = ConversationEngine(settings)
    engine.stt_client.listen_and_transcribe = lambda max_seconds=None: "open ai"

    text, _utterance_end_time = engine.listen_once()

    assert text == "open ai"
