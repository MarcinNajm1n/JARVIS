from pathlib import Path

from src.memory_store import (
    MAKSYMALNA_LICZBA_WIADOMOSCI_HISTORII,
    ogranicz_historie,
    wczytaj_historie,
    zapisz_historie,
    wyczysc_historie,
)


def test_zapis_i_odczyt_historii(tmp_path: Path):
    sciezka_testowa = tmp_path / "conversation_history.json"

    historia = [
        {"role": "user", "content": "Cześć"},
        {"role": "assistant", "content": "Witaj"},
    ]

    zapisz_historie(historia, sciezka_testowa)
    wynik = wczytaj_historie(sciezka_testowa)

    assert wynik == historia


def test_ogranicz_historie_zostawia_40_ostatnich_wiadomosci():
    historia = [
        {"role": "user", "content": f"Wiadomosc {indeks}"}
        for indeks in range(55)
    ]

    wynik = ogranicz_historie(historia)

    assert len(wynik) == MAKSYMALNA_LICZBA_WIADOMOSCI_HISTORII
    assert wynik[0]["content"] == "Wiadomosc 15"
    assert wynik[-1]["content"] == "Wiadomosc 54"


def test_zapisz_historie_ucina_plik_do_40_ostatnich_wiadomosci(tmp_path: Path):
    sciezka_testowa = tmp_path / "conversation_history.json"
    historia = [
        {"role": "assistant", "content": f"Odpowiedz {indeks}"}
        for indeks in range(45)
    ]

    zapisz_historie(historia, sciezka_testowa)
    wynik = wczytaj_historie(sciezka_testowa)

    assert len(wynik) == 40, "conversation_history.json powinien miec twardy limit 40 wpisow"
    assert wynik[0]["content"] == "Odpowiedz 5", "zapis powinien usuwac najstarsze wpisy"
    assert wynik[-1]["content"] == "Odpowiedz 44", "zapis powinien zachowac najnowszy wpis"


def test_wczytaj_historie_ucina_stary_rozrosniety_plik_do_40_wiadomosci(tmp_path: Path):
    sciezka_testowa = tmp_path / "conversation_history.json"
    historia = [
        {"role": "user", "content": f"Stara wiadomosc {indeks}"}
        for indeks in range(80)
    ]
    zapisz_historie(historia, sciezka_testowa, limit=80)

    wynik = wczytaj_historie(sciezka_testowa)

    assert len(wynik) == 40
    assert wynik[0]["content"] == "Stara wiadomosc 40"
    assert wynik[-1]["content"] == "Stara wiadomosc 79"


def test_wczytaj_historie_z_uszkodzonym_json_zwraca_pusta_liste(tmp_path: Path):
    sciezka_testowa = tmp_path / "conversation_history.json"
    sciezka_testowa.write_text("{to nie jest poprawny json", encoding="utf-8")

    wynik = wczytaj_historie(sciezka_testowa)

    assert wynik == [], "uszkodzony conversation_history.json nie powinien wykrzaczyc startu"


def test_wczytaj_historie_z_obiektem_zamiast_listy_zwraca_pusta_liste(tmp_path: Path):
    sciezka_testowa = tmp_path / "conversation_history.json"
    sciezka_testowa.write_text('{"role": "user", "content": "bledny format"}', encoding="utf-8")

    wynik = wczytaj_historie(sciezka_testowa)

    assert wynik == [], "historia musi byc lista wiadomosci, inaczej engine dostanie zly format"


def test_wczytaj_historie_gdy_plik_nie_istnieje(tmp_path: Path):
    sciezka_testowa = tmp_path / "brak_pliku.json"

    wynik = wczytaj_historie(sciezka_testowa)

    assert wynik == []


def test_wyczysc_historie(tmp_path: Path):
    sciezka_testowa = tmp_path / "conversation_history.json"

    historia = [
        {"role": "user", "content": "Test"}
    ]

    zapisz_historie(historia, sciezka_testowa)
    wyczysc_historie(sciezka_testowa)

    wynik = wczytaj_historie(sciezka_testowa)

    assert wynik == []
