from pathlib import Path

from src.long_term_memory import (
    dodaj_do_pamieci_stalej,
    dodaj_wpis_pamieci,
    edytuj_wpis_pamieci,
    formatuj_pamiec_stala,
    formatuj_memory_review,
    szukaj_pamieci,
    usun_wpis_pamieci,
    wczytaj_pamiec_stala,
    wyczysc_pamiec_stala,
    zapisz_pamiec_stala,
)


def test_dodaj_do_pamieci_stalej():
    pamiec = []

    pamiec = dodaj_do_pamieci_stalej(pamiec, "Studiuje mechatronike.")

    assert pamiec == ["Studiuje mechatronike."]


def test_dodaj_do_pamieci_stalej_bez_duplikatow():
    pamiec = ["Studiuje mechatronike."]

    pamiec = dodaj_do_pamieci_stalej(pamiec, "Studiuje mechatronike.")

    assert pamiec == ["Studiuje mechatronike."]


def test_zapis_i_odczyt_pamieci_stalej(tmp_path: Path):
    sciezka_testowa = tmp_path / "long_term_memory.json"

    pamiec = [
        "Mam na imie Kornel.",
        "Buduje projekt Jarvis.",
    ]

    zapisz_pamiec_stala(pamiec, sciezka_testowa)
    wynik = wczytaj_pamiec_stala(sciezka_testowa)

    assert wynik == pamiec


def test_wyczysc_pamiec_stala(tmp_path: Path):
    sciezka_testowa = tmp_path / "long_term_memory.json"

    pamiec = ["Test pamieci stalej."]

    zapisz_pamiec_stala(pamiec, sciezka_testowa)
    wyczysc_pamiec_stala(sciezka_testowa)

    wynik = wczytaj_pamiec_stala(sciezka_testowa)

    assert wynik == []


def test_formatuj_pusta_pamiec_stala():
    wynik = formatuj_pamiec_stala([])

    assert wynik == "Pamiec stala jest pusta."


def test_formatuj_pamiec_stala_z_wpisami():
    pamiec = [
        "Mam na imie Kornel.",
        "Studiuje mechatronike.",
    ]

    wynik = formatuj_pamiec_stala(pamiec)

    assert "1. [facts] Mam na imie Kornel." in wynik
    assert "2. [facts] Studiuje mechatronike." in wynik


def test_dodaj_wpis_pamieci_twory_typed_entry():
    pamiec = []

    entry = dodaj_wpis_pamieci(pamiec, "Wole krotkie odpowiedzi.", "preferences")

    assert entry is not None
    assert entry["type"] == "preferences"
    assert entry["content"] == "Wole krotkie odpowiedzi."
    assert pamiec == [entry]


def test_edytuj_i_usun_wpis_pamieci():
    pamiec = []
    entry = dodaj_wpis_pamieci(pamiec, "Stary fakt.", "facts")

    updated = edytuj_wpis_pamieci(pamiec, entry["id"], "Nowy fakt.", "decisions")
    removed = usun_wpis_pamieci(pamiec, entry["id"])

    assert updated["content"] == "Nowy fakt."
    assert updated["type"] == "decisions"
    assert removed is True
    assert pamiec == []


def test_szukaj_pamieci_i_review_po_typach():
    pamiec = []
    dodaj_wpis_pamieci(pamiec, "Kornel woli techniczne odpowiedzi.", "preferences")

    wyniki = szukaj_pamieci(pamiec, "techniczne odpowiedzi")
    review = formatuj_memory_review(pamiec)

    assert wyniki[0]["type"] == "preferences"
    assert "[preferences]" in review
