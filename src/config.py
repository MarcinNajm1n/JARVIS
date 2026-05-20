from __future__ import annotations

import os
from dataclasses import dataclass
from enum import StrEnum
from functools import lru_cache
from pathlib import Path

from dotenv import load_dotenv


PROJECT_ROOT = Path(__file__).resolve().parents[1]
DEFAULT_TTS_VOICE = "onyx"
API_KEY_PLACEHOLDER_MARKERS = (
    "tu_wklej",
    "twoj_klucz",
    "your_api_key",
    "paste",
    "example",
)


def _bool_from_env(name: str, default: bool) -> bool:
    raw_value = os.getenv(name)
    if raw_value is None:
        return default

    return raw_value.strip().lower() in {"1", "true", "yes", "y", "tak", "on"}


def _int_from_env(name: str, default: int) -> int:
    raw_value = os.getenv(name)
    if raw_value is None:
        return default

    try:
        return int(raw_value)
    except ValueError:
        return default


def _float_from_env(name: str, default: float) -> float:
    raw_value = os.getenv(name)
    if raw_value is None:
        return default

    try:
        return float(raw_value)
    except ValueError:
        return default


def _speech_rms_threshold_from_env(default: int = 500) -> int:
    sensitivity = os.getenv("MICROPHONE_SENSITIVITY")
    if sensitivity is not None:
        normalized_sensitivity = sensitivity.strip().lower()
        thresholds = {
            "high": 320,
            "wysoka": 320,
            "normal": 500,
            "medium": 500,
            "srednia": 500,
            "low": 750,
            "niska": 750,
        }
        if normalized_sensitivity in thresholds:
            return thresholds[normalized_sensitivity]

    raw_threshold = os.getenv("SPEECH_RMS_THRESHOLD")
    if raw_threshold is not None:
        try:
            return int(raw_threshold)
        except ValueError:
            return default

    return default


def _path_from_env(name: str, default: str) -> Path:
    raw_value = os.getenv(name, default)
    path = Path(raw_value)
    if path.is_absolute():
        return path
    return PROJECT_ROOT / path


class VoiceOption(StrEnum):
    ALLOY = "alloy"
    ASH = "ash"
    BALLAD = "ballad"
    CORAL = "coral"
    ECHO = "echo"
    FABLE = "fable"
    NOVA = "nova"
    ONYX = "onyx"
    SAGE = "sage"
    SHIMMER = "shimmer"
    VERSE = "verse"


def _voice_from_env(name: str, default: str) -> str:
    raw_value = os.getenv(name, default).strip().lower()
    allowed = {voice.value for voice in VoiceOption}
    if raw_value not in allowed:
        return default
    return raw_value


def _normalize_secret(value: str | None) -> str | None:
    if value is None:
        return None

    normalized = value.strip().strip('"').strip("'").strip()
    return normalized or None


def _looks_like_placeholder_api_key(value: str) -> bool:
    normalized = value.strip().lower()
    if len(normalized) < 20:
        return True

    return any(marker in normalized for marker in API_KEY_PLACEHOLDER_MARKERS)


@dataclass(frozen=True)
class Settings:
    assistant_name: str
    openai_api_key: str | None
    llm_model: str
    stt_model: str
    tts_model: str
    tts_voice: str
    embedding_model: str
    system_prompt: str
    input_mode: str
    tts_enabled: bool
    rag_enabled: bool
    debug: bool
    log_level: str
    max_history_messages: int
    history_enabled: bool
    rag_top_k: int
    rag_chunk_size: int
    rag_chunk_overlap: int
    record_seconds: int
    wake_record_seconds: int
    command_timeout_seconds: int
    awake_confirmation_timeout_seconds: int
    speech_end_silence_seconds: float
    min_silence_ms: int
    audio_chunk_seconds: float
    speech_rms_threshold: int
    min_speech_seconds: float
    sample_rate: int
    stt_language: str
    stt_prompt: str
    transcript_correction_enabled: bool
    transcript_correction_with_llm: bool
    transcript_correction_min_confidence: float
    wake_phrase: str
    history_path: Path
    long_term_memory_path: Path
    documents_dir: Path
    vector_store_dir: Path
    tts_output_path: Path
    microphone_temp_path: Path
    user_profile_path: Path
    task_store_path: Path
    project_store_path: Path
    assistant_state_path: Path
    tool_call_log_path: Path
    conversation_summary_path: Path
    episodic_memory_path: Path
    cost_log_path: Path
    feedback_path: Path
    chroma_collection: str
    tts_async_playback: bool
    auto_memory_enabled: bool
    terminal_ui: bool
    function_calling_enabled: bool
    low_latency_mode: bool
    streaming_llm: bool
    streaming_tts: bool
    post_speech_sleep_delay_seconds: float
    response_text_clear_delay_seconds: float
    follow_up_timeout_seconds: int
    gpt_4_1_mini_input_cost_per_1m: float
    gpt_4_1_mini_output_cost_per_1m: float
    latency_budget_seconds: float
    latency_critical_seconds: float
    chunk_ms: int
    avg_rtt_ms: int
    tokens_per_s: int


DEFAULT_SYSTEM_PROMPT = """
Jestes JARVIS-em, prywatnym asystentem technicznym uzytkownika.
Odpowiadasz po polsku, konkretnie i praktycznie.
Twoj styl jest inspirowany filmowym asystentem J.A.R.V.I.S. z Iron Mana:
spokojny, precyzyjny, elegancki, techniczny i lekko ironiczny, ale bez
teatralnosci, bez przesadnego slangu i bez cytowania kwestii z filmu.
Masz brzmiec jak kompetentny system pokladowy prywatnego laboratorium:
najpierw diagnoza, potem rekomendacja, potem nastepny krok.
Uzytkownik jest studentem mechatroniki i rozwija projekt AI w Pythonie.
Pomagasz jak mentor techniczny: jasno, inzyniersko i krok po kroku.
Nie wymyslasz faktow. Jesli czegos nie wiesz, mowisz to wprost.
Nie proponujesz computer vision, YOLO, robotyki, kamer ani sterowania sprzetem,
bo obecny zakres projektu obejmuje tylko mozg, rozmowe, pamiec i glos.
""".strip()


@lru_cache(maxsize=1)
def load_settings() -> Settings:
    load_dotenv(PROJECT_ROOT / ".env", override=True)

    input_mode = os.getenv("JARVIS_RUNTIME_INPUT_MODE") or os.getenv("INPUT_MODE", "text")
    input_mode = input_mode.strip().lower()
    if input_mode not in {"text", "voice", "wake"}:
        input_mode = "text"

    return Settings(
        assistant_name=os.getenv("ASSISTANT_NAME", "JARVIS"),
        openai_api_key=_normalize_secret(os.getenv("OPENAI_API_KEY")),
        llm_model=os.getenv("LLM_MODEL", "gpt-4.1-mini"),
        stt_model=os.getenv("STT_MODEL", "whisper-1"),
        tts_model=os.getenv("TTS_MODEL", "gpt-4o-mini-tts"),
        tts_voice=_voice_from_env("TTS_VOICE", DEFAULT_TTS_VOICE),
        embedding_model=os.getenv("EMBEDDING_MODEL", "text-embedding-3-small"),
        system_prompt=os.getenv("SYSTEM_PROMPT", DEFAULT_SYSTEM_PROMPT),
        input_mode=input_mode,
        tts_enabled=_bool_from_env("TTS_ENABLED", True),
        rag_enabled=_bool_from_env("RAG_ENABLED", True),
        debug=_bool_from_env("DEBUG", False),
        log_level=os.getenv("LOG_LEVEL", "INFO"),
        max_history_messages=_int_from_env("MAX_HISTORY_MESSAGES", 40),
        history_enabled=_bool_from_env("HISTORY_ENABLED", True),
        rag_top_k=_int_from_env("RAG_TOP_K", 4),
        rag_chunk_size=_int_from_env("RAG_CHUNK_SIZE", 900),
        rag_chunk_overlap=_int_from_env("RAG_CHUNK_OVERLAP", 120),
        record_seconds=_int_from_env(
            "MAX_RECORD_SECONDS",
            _int_from_env("RECORD_SECONDS", 12),
        ),
        wake_record_seconds=_int_from_env("WAKE_RECORD_SECONDS", 4),
        command_timeout_seconds=_int_from_env("COMMAND_TIMEOUT_SECONDS", 10),
        awake_confirmation_timeout_seconds=_int_from_env(
            "AWAKE_CONFIRMATION_TIMEOUT_SECONDS",
            10,
        ),
        speech_end_silence_seconds=_float_from_env(
            "SPEECH_END_SILENCE_SECONDS",
            _int_from_env("MIN_SILENCE_MS", 650) / 1000,
        ),
        min_silence_ms=_int_from_env("MIN_SILENCE_MS", 650),
        audio_chunk_seconds=_float_from_env("AUDIO_CHUNK_SECONDS", 0.2),
        speech_rms_threshold=_speech_rms_threshold_from_env(500),
        min_speech_seconds=_float_from_env("MIN_SPEECH_SECONDS", 0.35),
        sample_rate=_int_from_env("SAMPLE_RATE", 16000),
        stt_language=os.getenv("STT_LANGUAGE", "pl"),
        stt_prompt=os.getenv(
            "STT_PROMPT",
            "Rozmowa po polsku z asystentem technicznym JARVIS.",
        ),
        wake_phrase=os.getenv("WAKE_PHRASE", "jarvis śpisz?"),
        transcript_correction_enabled=_bool_from_env("TRANSCRIPT_CORRECTION_ENABLED", True),
        transcript_correction_with_llm=_bool_from_env("TRANSCRIPT_CORRECTION_WITH_LLM", False),
        transcript_correction_min_confidence=_float_from_env(
            "TRANSCRIPT_CORRECTION_MIN_CONFIDENCE",
            0.65,
        ),
        history_path=_path_from_env("HISTORY_PATH", "data/conversation_history.json"),
        long_term_memory_path=_path_from_env(
            "LONG_TERM_MEMORY_PATH",
            "data/long_term_memory.json",
        ),
        documents_dir=_path_from_env("DOCUMENTS_DIR", "data/documents"),
        vector_store_dir=_path_from_env("VECTOR_STORE_DIR", "data/vector_store"),
        tts_output_path=_path_from_env("TTS_OUTPUT_PATH", "data/tts_output.mp3"),
        microphone_temp_path=_path_from_env("MICROPHONE_TEMP_PATH", "data/mic_input.wav"),
        user_profile_path=_path_from_env("USER_PROFILE_PATH", "data/user_profile.json"),
        task_store_path=_path_from_env("TASK_STORE_PATH", "data/tasks.json"),
        project_store_path=_path_from_env("PROJECT_STORE_PATH", "data/projects.json"),
        assistant_state_path=_path_from_env("ASSISTANT_STATE_PATH", "data/assistant_state.json"),
        tool_call_log_path=_path_from_env("TOOL_CALL_LOG_PATH", "data/tool_calls.json"),
        conversation_summary_path=_path_from_env(
            "CONVERSATION_SUMMARY_PATH",
            "data/conversation_summary.json",
        ),
        episodic_memory_path=_path_from_env("EPISODIC_MEMORY_PATH", "data/episodic_memory.json"),
        cost_log_path=_path_from_env("COST_LOG_PATH", "data/usage_costs.json"),
        feedback_path=_path_from_env("FEEDBACK_PATH", "data/feedback.json"),
        chroma_collection=os.getenv("CHROMA_COLLECTION", "jarvis_memory"),
        tts_async_playback=_bool_from_env("TTS_ASYNC_PLAYBACK", True),
        auto_memory_enabled=_bool_from_env("AUTO_MEMORY_ENABLED", True),
        terminal_ui=_bool_from_env("TERMINAL_UI", True),
        function_calling_enabled=_bool_from_env("FUNCTION_CALLING_ENABLED", True),
        low_latency_mode=_bool_from_env("LOW_LATENCY_MODE", False),
        streaming_llm=_bool_from_env("STREAMING_LLM", False),
        streaming_tts=_bool_from_env("STREAMING_TTS", False),
        post_speech_sleep_delay_seconds=_float_from_env(
            "POST_SPEECH_SLEEP_DELAY_SECONDS",
            5.0,
        ),
        response_text_clear_delay_seconds=_float_from_env(
            "RESPONSE_TEXT_CLEAR_DELAY_SECONDS",
            1.0,
        ),
        follow_up_timeout_seconds=_int_from_env("FOLLOW_UP_TIMEOUT_SECONDS", 10),
        gpt_4_1_mini_input_cost_per_1m=_float_from_env(
            "GPT_4_1_MINI_INPUT_COST_PER_1M",
            0.40,
        ),
        gpt_4_1_mini_output_cost_per_1m=_float_from_env(
            "GPT_4_1_MINI_OUTPUT_COST_PER_1M",
            1.60,
        ),
        latency_budget_seconds=_float_from_env("LATENCY_BUDGET_SECONDS", 2.0),
        latency_critical_seconds=_float_from_env("LATENCY_CRITICAL_SECONDS", 3.0),
        chunk_ms=_int_from_env("CHUNK_MS", 450),
        avg_rtt_ms=_int_from_env("AVG_RTT_MS", 900),
        tokens_per_s=_int_from_env("TOKENS_PER_S", 40),
    )


def require_openai_api_key(settings: Settings | None = None) -> str:
    active_settings = settings or load_settings()
    if not active_settings.openai_api_key:
        raise ValueError(
            "Brakuje OPENAI_API_KEY. Utworz plik .env i wpisz prawdziwy klucz API."
        )

    if _looks_like_placeholder_api_key(active_settings.openai_api_key):
        raise ValueError(
            "OPENAI_API_KEY w pliku .env wyglada jak przykladowa wartosc. "
            "Zastap cala linie prawdziwym kluczem API z platform.openai.com."
        )

    return active_settings.openai_api_key
