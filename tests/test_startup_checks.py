import os
from dataclasses import replace

from src.config import load_settings
from src.startup_checks import (
    EnvFileDiagnostics,
    RUNTIME_INPUT_MODE_ENV,
    STARTUP_WARNINGS_ENV,
    evaluate_startup,
    inspect_env_file,
    prepare_runtime_environment,
    read_startup_warnings,
)


def test_startup_check_przelacza_wake_na_tryb_tekstowy_gdy_mikrofon_padnie():
    settings = replace(
        load_settings(),
        input_mode="wake",
        openai_api_key="unit-test-openai-key-value-for-diagnostics",
    )

    result = evaluate_startup(
        settings=settings,
        env_file_exists=True,
        microphone_ok=False,
        microphone_message="brak urzadzenia",
    )

    assert result.input_mode == "text"
    assert any("Mikrofon jest niedostepny" in warning for warning in result.warnings)


def test_startup_check_ostrzega_o_braku_env_i_klucza_api():
    settings = replace(load_settings(), input_mode="text", openai_api_key=None)

    result = evaluate_startup(
        settings=settings,
        env_file_exists=False,
        microphone_ok=True,
    )

    assert result.input_mode == "text"
    assert any("Nie znaleziono pliku .env" in warning for warning in result.warnings)
    assert any("Brakuje OPENAI_API_KEY" in warning for warning in result.warnings)


def test_inspect_env_file_wykrywa_bom_duplikat_i_cudzyslowy(tmp_path):
    env_path = tmp_path / ".env"
    env_path.write_text(
        'OPENAI_API_KEY="unit-test-openai-key-value-for-diagnostics"\n'
        "OPENAI_API_KEY= drugi\n",
        encoding="utf-8-sig",
    )

    diagnostics = inspect_env_file(env_path)

    assert diagnostics.has_bom is True
    assert diagnostics.openai_key_count == 2
    assert diagnostics.hidden_openai_key_count == 1
    assert diagnostics.openai_key_has_wrapping_quotes is True


def test_startup_check_pokazuje_czytelne_ostrzezenia_env():
    settings = replace(
        load_settings(),
        input_mode="text",
        openai_api_key="unit-test-openai-key-value-for-diagnostics",
    )

    result = evaluate_startup(
        settings=settings,
        env_file_exists=True,
        microphone_ok=True,
        env_diagnostics=EnvFileDiagnostics(
            exists=True,
            has_bom=True,
            openai_key_count=2,
            hidden_openai_key_count=1,
            openai_key_has_wrapping_quotes=True,
            openai_key_has_outer_whitespace=True,
        ),
    )

    assert any("Plik .env ma BOM" in warning for warning in result.warnings)
    assert any("wiecej niz jedna linie OPENAI_API_KEY" in warning for warning in result.warnings)
    assert any("ukryty znak BOM" in warning for warning in result.warnings)


def test_prepare_runtime_environment_zapisuje_ostrzezenia_do_env(monkeypatch):
    monkeypatch.delenv(RUNTIME_INPUT_MODE_ENV, raising=False)
    monkeypatch.delenv(STARTUP_WARNINGS_ENV, raising=False)
    monkeypatch.setattr("src.startup_checks.check_microphone_available", lambda: (False, "test"))

    result = prepare_runtime_environment()

    assert isinstance(result.warnings, tuple)
    assert read_startup_warnings() == list(result.warnings)
    assert STARTUP_WARNINGS_ENV in os.environ
    load_settings.cache_clear()
