from __future__ import annotations

import json
import os
from dataclasses import dataclass

from src.config import PROJECT_ROOT, Settings, load_settings, require_openai_api_key


STARTUP_WARNINGS_ENV = "JARVIS_STARTUP_WARNINGS"
RUNTIME_INPUT_MODE_ENV = "JARVIS_RUNTIME_INPUT_MODE"


@dataclass(frozen=True)
class StartupCheckResult:
    input_mode: str
    warnings: tuple[str, ...]


def prepare_runtime_environment() -> StartupCheckResult:
    load_settings.cache_clear()
    settings = load_settings()
    microphone_ok, microphone_message = check_microphone_available()
    result = evaluate_startup(
        settings=settings,
        env_file_exists=(PROJECT_ROOT / ".env").exists(),
        microphone_ok=microphone_ok,
        microphone_message=microphone_message,
    )

    if result.input_mode != settings.input_mode:
        os.environ[RUNTIME_INPUT_MODE_ENV] = result.input_mode
        load_settings.cache_clear()

    os.environ[STARTUP_WARNINGS_ENV] = json.dumps(
        list(result.warnings),
        ensure_ascii=False,
    )
    return result


def evaluate_startup(
    settings: Settings,
    env_file_exists: bool,
    microphone_ok: bool,
    microphone_message: str = "",
) -> StartupCheckResult:
    warnings: list[str] = []
    input_mode = settings.input_mode

    if not env_file_exists:
        warnings.append("Nie znaleziono pliku .env. Skopiuj .env.example do .env.")

    try:
        require_openai_api_key(settings)
    except ValueError as error:
        warnings.append(str(error))

    if settings.input_mode in {"voice", "wake"} and not microphone_ok:
        reason = microphone_message or "brak domyslnego urzadzenia wejsciowego"
        warnings.append(
            "Mikrofon jest niedostepny: "
            f"{reason}. Przelaczam JARVISA w awaryjny tryb tekstowy."
        )
        input_mode = "text"

    return StartupCheckResult(input_mode=input_mode, warnings=tuple(warnings))


def check_microphone_available() -> tuple[bool, str]:
    try:
        import sounddevice as sd
    except Exception as error:
        return False, f"nie mozna zaladowac sounddevice ({error})"

    try:
        device = sd.query_devices(kind="input")
    except Exception as error:
        return False, f"nie mozna odczytac domyslnego mikrofonu ({error})"

    if not device:
        return False, "nie znaleziono domyslnego mikrofonu"

    return True, ""


def read_startup_warnings() -> list[str]:
    raw_value = os.getenv(STARTUP_WARNINGS_ENV)
    if not raw_value:
        return []

    try:
        loaded = json.loads(raw_value)
    except json.JSONDecodeError:
        return [raw_value]

    if not isinstance(loaded, list):
        return []

    return [str(item) for item in loaded if str(item).strip()]
