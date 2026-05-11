from pathlib import Path

from src.memory_store import (
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