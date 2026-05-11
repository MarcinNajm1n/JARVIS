import json
from pathlib import Path


SCIEZKA_PAMIECI_STALEJ = Path("data/long_term_memory.json")


def wczytaj_pamiec_stala() -> list[str]:
    if not SCIEZKA_PAMIECI_STALEJ.exists():
        return []

    with open(SCIEZKA_PAMIECI_STALEJ, "r", encoding="utf-8") as plik:
        return json.load(plik)


def zapisz_pamiec_stala(pamiec_stala: list[str]) -> None:
    SCIEZKA_PAMIECI_STALEJ.parent.mkdir(parents=True, exist_ok=True)

    with open(SCIEZKA_PAMIECI_STALEJ, "w", encoding="utf-8") as plik:
        json.dump(pamiec_stala, plik, ensure_ascii=False, indent=4)


def dodaj_do_pamieci_stalej(pamiec_stala: list[str], wpis: str) -> list[str]:
    wpis = wpis.strip()

    if wpis and wpis not in pamiec_stala:
        pamiec_stala.append(wpis)

    return pamiec_stala


def formatuj_pamiec_stala(pamiec_stala: list[str]) -> str:
    if len(pamiec_stala) == 0:
        return "Pamięć stała jest pusta."

    wynik = "Pamięć stała:\n"

    for indeks, wpis in enumerate(pamiec_stala, start=1):
        wynik += f"{indeks}. {wpis}\n"

    return wynik.strip()