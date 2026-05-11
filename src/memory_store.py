import json
from pathlib import Path


SCIEZKA_PAMIECI = Path("data/conversation_history.json")


def wczytaj_historie() -> list[dict]:
    if not SCIEZKA_PAMIECI.exists():
        return []

    with open(SCIEZKA_PAMIECI, "r", encoding="utf-8") as plik:
        return json.load(plik)


def zapisz_historie(historia: list[dict]) -> None:
    SCIEZKA_PAMIECI.parent.mkdir(parents=True, exist_ok=True)

    with open(SCIEZKA_PAMIECI, "w", encoding="utf-8") as plik:
        json.dump(historia, plik, ensure_ascii=False, indent=4)