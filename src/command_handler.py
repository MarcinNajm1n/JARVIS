from pathlib import Path

from config import NAZWA_ASYSTENTA, MODEL_LLM
from src.debug_utils import czy_debug_wlaczony, ustaw_debug
from src.long_term_memory import (
    SCIEZKA_PAMIECI_STALEJ,
    dodaj_do_pamieci_stalej,
    formatuj_pamiec_stala,
    zapisz_pamiec_stala,
    wyczysc_pamiec_stala,
)
from src.memory_store import SCIEZKA_HISTORII, wyczysc_historie


def pokaz_pomoc() -> None:
    print("Dostępne komendy:")
    print("/zapamietaj tresc       - zapisz informację do pamięci stałej")
    print("/pamiec                 - pokaż pamięć stałą")
    print("/wyczysc_pamiec         - wyczyść pamięć stałą")
    print("/wyczysc_historie       - wyczyść historię rozmowy")
    print("/reset                  - zresetuj kontekst rozmowy")
    print("/status                 - pokaż stan historii i pamięci")
    print("/model                  - pokaż aktualnie używany model LLM")
    print("/debug on               - włącz tryb debugowania")
    print("/debug off              - wyłącz tryb debugowania")
    print("/debug status           - pokaż status debugowania")
    print("/pomoc                  - pokaż dostępne komendy")
    print("exit                    - zakończ program")


def obsluz_komende(
    tekst_uzytkownika: str,
    historia: list[dict],
    pamiec_stala: list[str],
    sciezka_historii: Path = SCIEZKA_HISTORII,
    sciezka_pamieci_stalej: Path = SCIEZKA_PAMIECI_STALEJ,
) -> tuple[bool, list[dict], list[str]]:
    """
    Zwraca:
    - czy_obsluzono_komende
    - aktualna historia
    - aktualna pamięć stała
    """

    tekst = tekst_uzytkownika.lower()

    if tekst == "/pomoc":
        pokaz_pomoc()
        print()
        return True, historia, pamiec_stala

    if tekst == "/status":
        print(f"Historia rozmowy: {len(historia)} wiadomości")
        print(f"Pamięć stała: {len(pamiec_stala)} wpisów")
        print()
        return True, historia, pamiec_stala

    if tekst == "/model":
        print(f"{NAZWA_ASYSTENTA}: Aktualny model LLM: {MODEL_LLM}")
        print()
        return True, historia, pamiec_stala

    if tekst.startswith("/debug"):
        czesci = tekst.split()

        if len(czesci) == 1 or czesci[1] == "status":
            status = "włączony" if czy_debug_wlaczony() else "wyłączony"
            print(f"{NAZWA_ASYSTENTA}: Tryb debugowania jest {status}.")
            print()
            return True, historia, pamiec_stala

        if czesci[1] == "on":
            ustaw_debug(True)
            print(f"{NAZWA_ASYSTENTA}: Tryb debugowania został włączony.")
            print()
            return True, historia, pamiec_stala

        if czesci[1] == "off":
            ustaw_debug(False)
            print(f"{NAZWA_ASYSTENTA}: Tryb debugowania został wyłączony.")
            print()
            return True, historia, pamiec_stala

        print(f"{NAZWA_ASYSTENTA}: Użyj: /debug on, /debug off albo /debug status")
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

        zapisz_pamiec_stala(pamiec_stala, sciezka_pamieci_stalej)

        print(f"{NAZWA_ASYSTENTA}: Zapisałem to w pamięci stałej.")
        print()
        return True, historia, pamiec_stala

    if tekst == "/pamiec":
        print(formatuj_pamiec_stala(pamiec_stala))
        print()
        return True, historia, pamiec_stala

    if tekst == "/reset":
        historia = []
        wyczysc_historie(sciezka_historii)

        print(f"{NAZWA_ASYSTENTA}: Kontekst rozmowy został zresetowany.")
        print("Pamięć stała nie została naruszona.")
        print()

        return True, historia, pamiec_stala

    if tekst == "/wyczysc_pamiec":
        potwierdzenie = input(
            "Czy na pewno chcesz wyczyścić pamięć stałą? (tak/nie): "
        ).strip().lower()

        if potwierdzenie == "tak":
            pamiec_stala = []
            wyczysc_pamiec_stala(sciezka_pamieci_stalej)
            print(f"{NAZWA_ASYSTENTA}: Pamięć stała została wyczyszczona.")
        else:
            print(f"{NAZWA_ASYSTENTA}: Anulowano czyszczenie pamięci stałej.")

        print()
        return True, historia, pamiec_stala

    if tekst == "/wyczysc_historie":
        potwierdzenie = input(
            "Czy na pewno chcesz wyczyścić historię rozmowy? (tak/nie): "
        ).strip().lower()

        if potwierdzenie == "tak":
            historia = []
            wyczysc_historie(sciezka_historii)
            print(f"{NAZWA_ASYSTENTA}: Historia rozmowy została wyczyszczona.")
        else:
            print(f"{NAZWA_ASYSTENTA}: Anulowano czyszczenie historii.")

        print()
        return True, historia, pamiec_stala

    return False, historia, pamiec_stala