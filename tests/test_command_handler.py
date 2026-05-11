from src.command_handler import obsluz_komende


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


def test_obsluz_zapamietaj_dodaje_wpis():
    historia = []
    pamiec_stala = []

    czy_komenda, nowa_historia, nowa_pamiec = obsluz_komende(
        "/zapamietaj Testowa informacja.",
        historia,
        pamiec_stala
    )

    assert czy_komenda is True
    assert nowa_historia == historia
    assert "Testowa informacja." in nowa_pamiec


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