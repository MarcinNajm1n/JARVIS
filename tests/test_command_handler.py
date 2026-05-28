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
from src.voice_state import aktywny_provider_glosu


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


def test_obsluz_glosowe_komendy_stop_tts():
    historia = []
    pamiec_stala = []
    tts_client = _FakeTTSClient()

    for command in ["stop", "przestan", "przestań", "koniec", "skoncz", "skończ"]:
        czy_komenda, nowa_historia, nowa_pamiec = obsluz_komende(
            command,
            historia,
            pamiec_stala,
            tts_client=tts_client,
        )

        assert czy_komenda is True
        assert nowa_historia == historia
        assert nowa_pamiec == pamiec_stala

    assert tts_client.stop_calls == 6


def test_obsluz_voice_provider_switch():
    czy_komenda, _historia, _pamiec = obsluz_komende(
        "/voice elevenlabs",
        [],
        [],
    )

    assert czy_komenda is True
    assert aktywny_provider_glosu() == "elevenlabs"

    obsluz_komende("/voice openai", [], [])
    assert aktywny_provider_glosu() == "openai"


def test_obsluz_memory_review(capsys):
    historia = []
    pamiec_stala = [
        {
            "id": 1,
            "type": "preferences",
            "content": "Wole krotkie odpowiedzi.",
            "created_at": None,
            "updated_at": None,
        }
    ]

    czy_komenda, nowa_historia, nowa_pamiec = obsluz_komende(
        "/memory review",
        historia,
        pamiec_stala,
    )
    output = capsys.readouterr().out

    assert czy_komenda is True
    assert nowa_historia == historia
    assert nowa_pamiec == pamiec_stala


def test_obsluz_env_status_nie_ujawnia_pelnego_klucza(capsys, monkeypatch):
    monkeypatch.setattr(
        "src.command_handler.format_openai_api_key_diagnostics",
        lambda: "OPENAI_API_KEY: present; length=44; prefix=unit; suffix=tics; sha8=abc12345",
    )

    czy_komenda, nowa_historia, nowa_pamiec = obsluz_komende(
        "/env status",
        [],
        [],
    )
    output = capsys.readouterr().out

    assert czy_komenda is True
    assert nowa_historia == []
    assert nowa_pamiec == []
    assert "OPENAI_API_KEY: present" in output
    assert "sha8=" in output
    assert "unit-test-openai-key-value-for-diagnostics" not in output


def test_obsluz_feedback_dobra(monkeypatch):
    fake_store = _FakeFeedbackStore()
    monkeypatch.setattr("src.command_handler.FeedbackStore", lambda: fake_store)

    czy_komenda, _historia, _pamiec = obsluz_komende(
        "/feedback dobra trafiona odpowiedz",
        [],
        [],
    )

    assert czy_komenda is True
    assert fake_store.items == [("dobra", "trafiona odpowiedz")]


class _FakeTTSClient:
    def __init__(self):
        self.stop_calls = 0

    def stop(self):
        self.stop_calls += 1


class _FakeFeedbackStore:
    def __init__(self):
        self.items = []

    def add(self, rating, note=""):
        self.items.append((rating, note))


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
