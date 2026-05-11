from config import NAZWA_ASYSTENTA
from src.long_term_memory import (
    dodaj_do_pamieci_stalej,
    formatuj_pamiec_stala,
    zapisz_pamiec_stala,
    wyczysc_pamiec_stala,
)
from src.memory_store import wyczysc_historie


def pokaz_pomoc() -> None:
    print("Dostępne komendy:")
    print("/zapamietaj tresc       - zapisz informację do pamięci stałej")
    print("/pamiec                 - pokaż pamięć stałą")
    print("/wyczysc_pamiec         - wyczyść pamięć stałą")
    print("/wyczysc_historie       - wyczyść historię rozmowy")
    print("/status                 - pokaż stan historii i pamięci")
    print("/pomoc                  - pokaż dostępne komendy")
    print("exit                    - zakończ program")


def obsluz_komende(
    tekst_uzytkownika: str,
    historia: list[dict],
    pamiec_stala: list[str]
) -> tuple[bool, list[dict], list[str]]:
    """
    Zwraca:
    - czy_obsluzono_komende
    - aktualna historia
    - aktualna pamięć stała
    """

    if tekst_uzytkownika.lower() == "/pomoc":
        pokaz_pomoc()
        print()
        return True, historia, pamiec_stala

    if tekst_uzytkownika.lower() == "/status":
        print(f"Historia rozmowy: {len(historia)} wiadomości")
        print(f"Pamięć stała: {len(pamiec_stala)} wpisów")
        print()
        return True, historia, pamiec_stala

    if tekst_uzytkownika.lower().startswith("/zapamietaj"):
        tresc_do_zapamietania = tekst_uzytkownika[len("/zapamietaj"):].strip()

        if tresc_do_zapamietania == "":
            print(f"{NAZWA_ASYSTENTA}: Użyj komendy w formie: /zapamietaj twoja_tresc")
            print()
            return True, historia, pamiec_stala

        pamiec_stala = dodaj_do_pamieci_stalej(
            pamiec_stala,
            tresc_do_zapamietania
        )
        zapisz_pamiec_stala(pamiec_stala)

        print(f"{NAZWA_ASYSTENTA}: Zapisałem to w pamięci stałej.")
        print()
        return True, historia, pamiec_stala

    if tekst_uzytkownika.lower() == "/pamiec":
        print(formatuj_pamiec_stala(pamiec_stala))
        print()
        return True, historia, pamiec_stala

    if tekst_uzytkownika.lower() == "/wyczysc_pamiec":
        potwierdzenie = input(
            "Czy na pewno chcesz wyczyścić pamięć stałą? (tak/nie): "
        ).strip().lower()

        if potwierdzenie == "tak":
            pamiec_stala = []
            wyczysc_pamiec_stala()
            print(f"{NAZWA_ASYSTENTA}: Pamięć stała została wyczyszczona.")
        else:
            print(f"{NAZWA_ASYSTENTA}: Anulowano czyszczenie pamięci stałej.")

        print()
        return True, historia, pamiec_stala

    if tekst_uzytkownika.lower() == "/wyczysc_historie":
        potwierdzenie = input(
            "Czy na pewno chcesz wyczyścić historię rozmowy? (tak/nie): "
        ).strip().lower()

        if potwierdzenie == "tak":
            historia = []
            wyczysc_historie()
            print(f"{NAZWA_ASYSTENTA}: Historia rozmowy została wyczyszczona.")
        else:
            print(f"{NAZWA_ASYSTENTA}: Anulowano czyszczenie historii.")

        print()
        return True, historia, pamiec_stala

    return False, historia, pamiec_stala