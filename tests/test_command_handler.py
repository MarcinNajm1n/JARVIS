from pathlib import Path

from src.command_handler import obsluz_komende
from src.long_term_memory import (
    wczytaj_pamiec_stala,
    zapisz_pamiec_stala,
)
from src.memory_store import (
    wczytaj_historie,
    zapisz_historie,
)


def test_obsluz_pomoc():
    historia = []
    pamiec_stala = []

    czy_komenda, nowa_historia, nowa_pamiec = obsluz_komende(
        "/pomoc",
        historia,
        pamiec_stala
    )

    assert czy_komenda is True
    assert nowa_historia == historia
    assert nowa_pamiec == pamiec_stala


def test_obsluz_status():
    historia = [
        {"role": "user", "content": "Cześć"}
    ]
    pamiec_stala = [
        "Mam na imię Kornel."
    ]

    czy_komenda, nowa_historia, nowa_pamiec = obsluz_komende(
        "/status",
        historia,
        pamiec_stala
    )

    assert czy_komenda is True
    assert nowa_historia == historia
    assert nowa_pamiec == pamiec_stala


def test_obsluz_model():
    historia = []
    pamiec_stala = []

    czy_komenda, nowa_historia, nowa_pamiec = obsluz_komende(
        "/model",
        historia,
        pamiec_stala
    )

    assert czy_komenda is True
    assert nowa_historia == historia
    assert nowa_pamiec == pamiec_stala


def test_obsluz_zapamietaj_dodaje_wpis_do_testowego_pliku(tmp_path: Path):
    historia = []
    pamiec_stala = []
    sciezka_testowa_pamieci = tmp_path / "long_term_memory.json"

    czy_komenda, nowa_historia, nowa_pamiec = obsluz_komende(
        "/zapamietaj Testowa informacja.",
        historia,
        pamiec_stala,
        sciezka_pamieci_stalej=sciezka_testowa_pamieci
    )

    zapisana_pamiec = wczytaj_pamiec_stala(sciezka_testowa_pamieci)

    assert czy_komenda is True
    assert nowa_historia == historia
    assert "Testowa informacja." in nowa_pamiec
    assert "Testowa informacja." in zapisana_pamiec


def test_obsluz_reset_czysci_tylko_testowa_historie(tmp_path: Path):
    historia = [
        {"role": "user", "content": "Cześć"},
        {"role": "assistant", "content": "Witaj"},
    ]
    pamiec_stala = ["Mam na imię Kornel."]
    sciezka_testowa_historii = tmp_path / "conversation_history.json"

    czy_komenda, nowa_historia, nowa_pamiec = obsluz_komende(
        "/reset",
        historia,
        pamiec_stala,
        sciezka_historii=sciezka_testowa_historii
    )

    zapisana_historia = wczytaj_historie(sciezka_testowa_historii)

    assert czy_komenda is True
    assert nowa_historia == []
    assert nowa_pamiec == pamiec_stala
    assert zapisana_historia == []


def test_zwykla_wiadomosc_nie_jest_komenda():
    historia = []
    pamiec_stala = []

    czy_komenda, nowa_historia, nowa_pamiec = obsluz_komende(
        "Co to jest Python?",
        historia,
        pamiec_stala
    )

    assert czy_komenda is False
    assert nowa_historia == historia
    assert nowa_pamiec == pamiec_stala
def test_wyczysc_pamiec_stala_po_potwierdzeniu_tak(tmp_path: Path, monkeypatch):
    historia = []
    pamiec_stala = ["Mam na imię Kornel."]
    sciezka_testowa_pamieci = tmp_path / "long_term_memory.json"

    zapisz_pamiec_stala(pamiec_stala, sciezka_testowa_pamieci)

    monkeypatch.setattr("builtins.input", lambda _: "tak")

    czy_komenda, nowa_historia, nowa_pamiec = obsluz_komende(
        "/wyczysc_pamiec",
        historia,
        pamiec_stala,
        sciezka_pamieci_stalej=sciezka_testowa_pamieci
    )

    zapisana_pamiec = wczytaj_pamiec_stala(sciezka_testowa_pamieci)

    assert czy_komenda is True
    assert nowa_historia == historia
    assert nowa_pamiec == []
    assert zapisana_pamiec == []
def test_wyczysc_pamiec_stala_po_potwierdzeniu_nie(tmp_path: Path, monkeypatch):
    historia = []
    pamiec_stala = ["Mam na imię Kornel."]
    sciezka_testowa_pamieci = tmp_path / "long_term_memory.json"

    zapisz_pamiec_stala(pamiec_stala, sciezka_testowa_pamieci)

    monkeypatch.setattr("builtins.input", lambda _: "nie")

    czy_komenda, nowa_historia, nowa_pamiec = obsluz_komende(
        "/wyczysc_pamiec",
        historia,
        pamiec_stala,
        sciezka_pamieci_stalej=sciezka_testowa_pamieci
    )

    zapisana_pamiec = wczytaj_pamiec_stala(sciezka_testowa_pamieci)

    assert czy_komenda is True
    assert nowa_historia == historia
    assert nowa_pamiec == pamiec_stala
    assert zapisana_pamiec == pamiec_stala
def test_wyczysc_historie_po_potwierdzeniu_tak(tmp_path: Path, monkeypatch):
    historia = [
        {"role": "user", "content": "Cześć"},
        {"role": "assistant", "content": "Witaj"},
    ]
    pamiec_stala = ["Mam na imię Kornel."]
    sciezka_testowa_historii = tmp_path / "conversation_history.json"

    zapisz_historie(historia, sciezka_testowa_historii)

    monkeypatch.setattr("builtins.input", lambda _: "tak")

    czy_komenda, nowa_historia, nowa_pamiec = obsluz_komende(
        "/wyczysc_historie",
        historia,
        pamiec_stala,
        sciezka_historii=sciezka_testowa_historii
    )

    zapisana_historia = wczytaj_historie(sciezka_testowa_historii)

    assert czy_komenda is True
    assert nowa_historia == []
    assert nowa_pamiec == pamiec_stala
    assert zapisana_historia == []
def test_wyczysc_historie_po_potwierdzeniu_nie(tmp_path: Path, monkeypatch):
    historia = [
        {"role": "user", "content": "Cześć"},
        {"role": "assistant", "content": "Witaj"},
    ]
    pamiec_stala = ["Mam na imię Kornel."]
    sciezka_testowa_historii = tmp_path / "conversation_history.json"

    zapisz_historie(historia, sciezka_testowa_historii)

    monkeypatch.setattr("builtins.input", lambda _: "nie")

    czy_komenda, nowa_historia, nowa_pamiec = obsluz_komende(
        "/wyczysc_historie",
        historia,
        pamiec_stala,
        sciezka_historii=sciezka_testowa_historii
    )

    zapisana_historia = wczytaj_historie(sciezka_testowa_historii)

    assert czy_komenda is True
    assert nowa_historia == historia
    assert nowa_pamiec == pamiec_stala
    assert zapisana_historia == historia