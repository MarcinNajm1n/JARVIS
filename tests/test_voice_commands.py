from src.voice_commands import (
    is_activation_command,
    is_shutdown_command,
    is_tts_stop_command,
)


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


def test_activation_command_rozumie_naturalne_warianty():
    for command in [
        "Jarvis śpisz?",
        "jarvis aktywacja",
        "jarvis aktywuj się",
        "jarvis obudź się",
        "jarvis online",
        "hej jarvis",
        "jervis wróć",
    ]:
        assert is_activation_command(command) is True


def test_activation_command_odrzuca_zwykle_zdanie():
    assert is_activation_command("sprawdz status projektu") is False


def test_shutdown_command_akceptuje_naturalne_warianty():
    for command in [
        "Jarvis wylacz sie",
        "Jarwis wyłącz się",
        "jarvis wyłącz się",
        "jarvis wylacz sie",
        "jarvis wylacz",
        "jarvis wyłącz",
        "jarvis dezaktywacja",
        "jarvis dezaktywuj sie",
        "jarvis zamknij program",
        "jarvis koniec pracy",
        "jarvis offline",
        "wylacz program",
    ]:
        assert is_shutdown_command(command) is True


def test_shutdown_command_odrzuca_zwykle_polecenie():
    assert is_shutdown_command("dodaj zadanie sprawdzic testy") is False
    assert is_shutdown_command("wylacz swiatlo w pokoju") is False
