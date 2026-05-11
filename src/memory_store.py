import json
from pathlib import Path


SCIEZKA_HISTORII = Path("data/conversation_history.json")


def wczytaj_historie(sciezka: Path = SCIEZKA_HISTORII) -> list[dict]:
    if not sciezka.exists():
        return []

    with open(sciezka, "r", encoding="utf-8") as plik:
        return json.load(plik)


def zapisz_historie(
    historia: list[dict],
    sciezka: Path = SCIEZKA_HISTORII
) -> None:
    sciezka.parent.mkdir(parents=True, exist_ok=True)

    with open(sciezka, "w", encoding="utf-8") as plik:
        json.dump(historia, plik, ensure_ascii=False, indent=4)


def wyczysc_historie(sciezka: Path = SCIEZKA_HISTORII) -> None:
    sciezka.parent.mkdir(parents=True, exist_ok=True)

    with open(sciezka, "w", encoding="utf-8") as plik:
        json.dump([], plik, ensure_ascii=False, indent=4)