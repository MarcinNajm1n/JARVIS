from src.stt import SpeechToTextClient
from src.web_app import _extract_command_after_wake_phrase


def test_contains_wake_phrase_akceptuje_jarvis_spisz():
    stt = SpeechToTextClient()

    assert stt.contains_wake_phrase("Jarvis śpisz?") is True
    assert stt.contains_wake_phrase("jarvis spisz") is True
    assert stt.contains_wake_phrase("d\u017carwis spisz") is True
    assert stt.contains_wake_phrase("jervis pisz") is True
    assert stt.contains_wake_phrase("jarwis czy spisz") is True
    assert stt.contains_wake_phrase("jarvis aktywacja") is True
    assert stt.contains_wake_phrase("jarvis obudz sie") is True


def test_contains_wake_phrase_odrzuca_zwykla_wypowiedz_bez_aktywacji():
    stt = SpeechToTextClient()

    assert stt.contains_wake_phrase("Dodaj zadanie do listy") is False


def test_extract_command_after_wake_phrase_zwraca_tylko_polecenie_po_aktywacji():
    wynik = _extract_command_after_wake_phrase(
        "jarvis śpisz? dodaj zadanie sprawdzic logi"
    )

    assert wynik == "dodaj zadanie sprawdzic logi"


def test_extract_command_after_wake_phrase_obsluguje_warianty_stt():
    stt = SpeechToTextClient()

    wynik = stt.extract_command_after_wake_phrase(
        "d\u017carwis spisz sprawdz status projektu"
    )

    assert wynik == "sprawdz status projektu"


def test_extract_command_after_wake_phrase_obsluguje_naturalna_aktywacje():
    stt = SpeechToTextClient()

    wynik = stt.extract_command_after_wake_phrase(
        "jarvis aktywacja sprawdz status projektu"
    )

    assert wynik == "sprawdz status projektu"


def test_extract_command_after_wake_phrase_blokuje_tekst_bez_aktywacji():
    wynik = _extract_command_after_wake_phrase("dodaj zadanie sprawdzic logi")

    assert wynik == ""
