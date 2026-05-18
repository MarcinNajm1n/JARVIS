from src.config import load_settings


_settings = load_settings()

NAZWA_ASYSTENTA = _settings.assistant_name
TRYB_TESTOWY = False
MODEL_LLM = _settings.llm_model
MAKSYMALNA_LICZBA_WIADOMOSCI = _settings.max_history_messages

MODEL_TTS = _settings.tts_model
GLOS_TTS = _settings.tts_voice
SCIEZKA_PLIKU_AUDIO = str(_settings.tts_output_path)

DEBUG = _settings.debug
MOWA_WLACZONA = _settings.tts_enabled
SYSTEM_PROMPT = _settings.system_prompt
