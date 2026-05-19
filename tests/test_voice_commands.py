from src.voice_commands import is_shutdown_command, is_tts_stop_command


def test_tts_stop_commands_akceptuja_polskie_warianty():
    for command in [
        "stop",
        "jarvis stop",
        "przestan",
        "przestań",
        "koniec",
        "skoncz",
        "skończ",
    ]:
        assert is_tts_stop_command(command) is True


def test_shutdown_command_akceptuje_jarvis_wylacz_sie():
    assert is_shutdown_command("Jarvis wyłącz się") is True
    assert is_shutdown_command("jarvis wylacz sie") is True


def test_shutdown_command_odrzuca_zwykle_polecenie():
    assert is_shutdown_command("dodaj zadanie sprawdzic testy") is False
