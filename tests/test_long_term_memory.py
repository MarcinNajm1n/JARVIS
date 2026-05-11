from pathlib import Path

from src.long_term_memory import (
    dodaj_do_pamieci_stalej,
    formatuj_pamiec_stala,
    wczytaj_pamiec_stala,
    zapisz_pamiec_stala,
    wyczysc_pamiec_stala,
)


def test_dodaj_do_pamieci_stalej():
    pamiec = []

    pamiec = dodaj_do_pamieci_stalej(pamiec, "Studiuję mechatronikę.")

    assert pamiec == ["Studiuję mechatronikę."]


def test_dodaj_do_pamieci_stalej_bez_duplikatow():
    pamiec = ["Studiuję mechatronikę."]

    pamiec = dodaj_do_pamieci_stalej(pamiec, "Studiuję mechatronikę.")

    assert pamiec == ["Studiuję mechatronikę."]


def test_zapis_i_odczyt_pamieci_stalej(tmp_path: Path):
    sciezka_testowa = tmp_path / "long_term_memory.json"

    pamiec = [
        "Mam na imię Kornel.",
        "Buduję projekt Jarvis."
    ]

    zapisz_pamiec_stala(pamiec, sciezka_testowa)
    wynik = wczytaj_pamiec_stala(sciezka_testowa)

    assert wynik == pamiec


def test_wyczysc_pamiec_stala(tmp_path: Path):
    sciezka_testowa = tmp_path / "long_term_memory.json"

    pamiec = ["Test pamięci stałej."]

    zapisz_pamiec_stala(pamiec, sciezka_testowa)
    wyczysc_pamiec_stala(sciezka_testowa)

    wynik = wczytaj_pamiec_stala(sciezka_testowa)

    assert wynik == []


def test_formatuj_pusta_pamiec_stala():
    wynik = formatuj_pamiec_stala([])

    assert wynik == "Pamięć stała jest pusta."


def test_formatuj_pamiec_stala_z_wpisami():
    pamiec = [
        "Mam na imię Kornel.",
        "Studiuję mechatronikę."
    ]

    wynik = formatuj_pamiec_stala(pamiec)

    assert "1. Mam na imię Kornel." in wynik
    assert "2. Studiuję mechatronikę." in wynik