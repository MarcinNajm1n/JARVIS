from __future__ import annotations

import json
import os
from dataclasses import dataclass
from pathlib import Path

from src.config import ENV_FILE_PATH, Settings, load_settings, require_openai_api_key


STARTUP_WARNINGS_ENV = "JARVIS_STARTUP_WARNINGS"
RUNTIME_INPUT_MODE_ENV = "JARVIS_RUNTIME_INPUT_MODE"


@dataclass(frozen=True)
class StartupCheckResult:
    input_mode: str
    warnings: tuple[str, ...]


@dataclass(frozen=True)
class EnvFileDiagnostics:
    exists: bool
    has_bom: bool = False
    openai_key_count: int = 0
    hidden_openai_key_count: int = 0
    openai_key_has_wrapping_quotes: bool = False
    openai_key_has_outer_whitespace: bool = False


def prepare_runtime_environment() -> StartupCheckResult:
    load_settings.cache_clear()
    settings = load_settings()
    env_diagnostics = inspect_env_file(ENV_FILE_PATH)
    microphone_ok, microphone_message = check_microphone_available()
    result = evaluate_startup(
        settings=settings,
        env_file_exists=env_diagnostics.exists,
        env_diagnostics=env_diagnostics,
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
    env_diagnostics: EnvFileDiagnostics | None = None,
) -> StartupCheckResult:
    warnings: list[str] = []
    input_mode = settings.input_mode

    if not env_file_exists:
        warnings.append("Nie znaleziono pliku .env. Skopiuj .env.example do .env.")
    if env_diagnostics is not None:
        warnings.extend(_format_env_diagnostic_warnings(env_diagnostics))

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


def inspect_env_file(path: Path = ENV_FILE_PATH) -> EnvFileDiagnostics:
    if not path.exists():
        return EnvFileDiagnostics(exists=False)

    data = path.read_bytes()
    has_bom = data.startswith(b"\xef\xbb\xbf")
    text = data.decode("utf-8-sig", errors="replace")
    openai_key_count = 0
    hidden_openai_key_count = 0
    openai_key_has_wrapping_quotes = False
    openai_key_has_outer_whitespace = False

    for line_index, line in enumerate(text.splitlines()):
        stripped = line.strip()
        if not stripped or stripped.startswith("#") or "=" not in line:
            continue
        key, raw_value = line.split("=", 1)
        key_without_bom = key.lstrip("\ufeff").strip()
        if key_without_bom != "OPENAI_API_KEY":
            continue
        openai_key_count += 1
        if key.startswith("\ufeff") or (has_bom and line_index == 0):
            hidden_openai_key_count += 1
        value = raw_value.rstrip("\r\n")
        if value != value.strip():
            openai_key_has_outer_whitespace = True
        normalized_value = value.strip()
        if (
            len(normalized_value) >= 2
            and normalized_value[0] == normalized_value[-1]
            and normalized_value[0] in {"'", '"'}
        ):
            openai_key_has_wrapping_quotes = True

    return EnvFileDiagnostics(
        exists=True,
        has_bom=has_bom,
        openai_key_count=openai_key_count,
        hidden_openai_key_count=hidden_openai_key_count,
        openai_key_has_wrapping_quotes=openai_key_has_wrapping_quotes,
        openai_key_has_outer_whitespace=openai_key_has_outer_whitespace,
    )


def _format_env_diagnostic_warnings(diagnostics: EnvFileDiagnostics) -> list[str]:
    warnings: list[str] = []
    if diagnostics.has_bom:
        warnings.append(
            "Plik .env ma BOM. Zapisz go jako UTF-8 bez BOM albo uruchom naprawe konfiguracji."
        )
    if diagnostics.hidden_openai_key_count:
        warnings.append(
            "OPENAI_API_KEY ma ukryty znak BOM przed nazwa klucza. To moze powodowac blad 401."
        )
    if diagnostics.openai_key_count > 1:
        warnings.append(
            "W pliku .env znaleziono wiecej niz jedna linie OPENAI_API_KEY. Zostaw tylko jedna."
        )
    if diagnostics.openai_key_has_wrapping_quotes:
        warnings.append(
            "OPENAI_API_KEY jest zapisany w cudzyslowach. Program je usunie, ale bezpieczniej zapisac klucz bez cudzyslowow."
        )
    if diagnostics.openai_key_has_outer_whitespace:
        warnings.append(
            "OPENAI_API_KEY ma spacje przed lub po wartosci. Program je usunie, ale warto oczyscic wpis w .env."
        )
    return warnings


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
