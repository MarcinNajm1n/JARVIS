import json
from pathlib import Path


SCIEZKA_HISTORII = Path("data/conversation_history.json")
MAKSYMALNA_LICZBA_WIADOMOSCI_HISTORII = 40


def ogranicz_historie(
    historia: list[dict],
    limit: int = MAKSYMALNA_LICZBA_WIADOMOSCI_HISTORII,
) -> list[dict]:
    if limit <= 0:
        return []

    return historia[-limit:]


def wczytaj_historie(
    sciezka: Path = SCIEZKA_HISTORII,
    limit: int = MAKSYMALNA_LICZBA_WIADOMOSCI_HISTORII,
) -> list[dict]:
    if not sciezka.exists():
        return []

    try:
        with open(sciezka, "r", encoding="utf-8") as plik:
            historia = json.load(plik)
    except (json.JSONDecodeError, OSError):
        return []

    if not isinstance(historia, list):
        return []

    return ogranicz_historie(historia, limit)


def zapisz_historie(
    historia: list[dict],
    sciezka: Path = SCIEZKA_HISTORII,
    limit: int = MAKSYMALNA_LICZBA_WIADOMOSCI_HISTORII,
) -> None:
    sciezka.parent.mkdir(parents=True, exist_ok=True)
    historia_do_zapisu = ogranicz_historie(historia, limit)

    with open(sciezka, "w", encoding="utf-8") as plik:
        json.dump(historia_do_zapisu, plik, ensure_ascii=False, indent=4)


def wyczysc_historie(sciezka: Path = SCIEZKA_HISTORII) -> None:
    zapisz_historie([], sciezka)
