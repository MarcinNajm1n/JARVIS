from dataclasses import replace


def test_load_settings_czyta_openai_key_z_env_utf8_bom(tmp_path, monkeypatch):
    import src.config as config

    env_path = tmp_path / ".env"
    env_path.write_text(
        "OPENAI_API_KEY=' unit-test-openai-key-value-for-diagnostics '\n",
        encoding="utf-8-sig",
    )
    monkeypatch.setattr(config, "PROJECT_ROOT", tmp_path)
    monkeypatch.setattr(config, "ENV_FILE_PATH", env_path)
    monkeypatch.delenv("OPENAI_API_KEY", raising=False)
    config.load_settings.cache_clear()

    settings = config.load_settings()

    assert settings.openai_api_key == "unit-test-openai-key-value-for-diagnostics"

    config.load_settings.cache_clear()


def test_openai_api_key_diagnostics_nie_ujawnia_pelnego_klucza():
    import src.config as config

    settings = replace(
        config.load_settings(),
        openai_api_key="unit-test-openai-key-value-for-diagnostics",
    )
    diagnostics = config.openai_api_key_diagnostics(settings)
    formatted = config.format_openai_api_key_diagnostics(settings)

    assert diagnostics["present"] is True
    assert diagnostics["suffix"] == "tics"
    assert "unit-test-openai-key-value-for-diagnostics" not in formatted
