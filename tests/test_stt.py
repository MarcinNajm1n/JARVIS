from src.stt import SpeechToTextClient
from src.web_app import _extract_command_after_wake_phrase


def test_contains_wake_phrase_akceptuje_jarvis_spisz():
    stt = SpeechToTextClient()

    assert stt.contains_wake_phrase("Jarvis śpisz?") is True
    assert stt.contains_wake_phrase("jarvis spisz") is True


def test_contains_wake_phrase_odrzuca_zwykla_wypowiedz_bez_aktywacji():
    stt = SpeechToTextClient()

    assert stt.contains_wake_phrase("Dodaj zadanie do listy") is False


def test_extract_command_after_wake_phrase_zwraca_tylko_polecenie_po_aktywacji():
    wynik = _extract_command_after_wake_phrase(
        "jarvis śpisz? dodaj zadanie sprawdzic logi"
    )

    assert wynik == "dodaj zadanie sprawdzic logi"


def test_extract_command_after_wake_phrase_blokuje_tekst_bez_aktywacji():
    wynik = _extract_command_after_wake_phrase("dodaj zadanie sprawdzic logi")

    assert wynik == ""
