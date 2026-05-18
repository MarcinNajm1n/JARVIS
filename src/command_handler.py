from __future__ import annotations

from pathlib import Path
from typing import Any

from config import MODEL_LLM, NAZWA_ASYSTENTA
from src.briefing import build_briefing
from src.debug_utils import czy_debug_wlaczony, ustaw_debug
from src.long_term_memory import (
    SCIEZKA_PAMIECI_STALEJ,
    dodaj_do_pamieci_stalej,
    formatuj_pamiec_stala,
    wyczysc_pamiec_stala,
    zapisz_pamiec_stala,
)
from src.memory_store import SCIEZKA_HISTORII, wyczysc_historie
from src.response_modes import list_modes
from src.voice_state import czy_mowa_wlaczona, ustaw_mowe


def pokaz_pomoc() -> None:
    print("Dostepne komendy:")
    print("/zapamietaj tresc       - zapisz informacje do pamieci stalej")
    print("/pamiec                 - pokaz pamiec stala")
    print("/wyczysc_pamiec         - wyczysc pamiec stala")
    print("/wyczysc_historie       - wyczysc historie rozmowy")
    print("/reset                  - zresetuj kontekst rozmowy")
    print("/status                 - pokaz stan historii, pamieci i glosu")
    print("/model                  - pokaz aktualny model LLM")
    print("/voice on/off/status    - wlacz, wylacz lub sprawdz TTS")
    print("/stop                   - przerwij aktualne odtwarzanie TTS")
    print("/debug on/off/status    - wlacz, wylacz lub sprawdz debug")
    print("/rag status             - pokaz stan lokalnej bazy wiedzy")
    print("/rag index              - przebuduj indeks dokumentow")
    print("/mode nazwa             - tryb: jarvis, mentor, szybki, techniczny")
    print("/profile                - pokaz profil uzytkownika")
    print("/profile set k v        - ustaw pole profilu")
    print("/task add tresc         - dodaj zadanie")
    print("/task list              - pokaz zadania")
    print("/task done id           - oznacz zadanie jako wykonane")
    print("/project nazwa          - ustaw aktywny projekt")
    print("/project log tresc      - dodaj notatke do projektu")
    print("/briefing               - dzienny briefing operacyjny")
    print("/input text             - przelacz wejscie na klawiature")
    print("/input voice            - przelacz wejscie na mikrofon")
    print("/input wake             - nasluchuj frazy 'jarvis aktywacja'")
    print("/pomoc                  - pokaz dostepne komendy")
    print("exit                    - zakoncz program")


def obsluz_komende(
    tekst_uzytkownika: str,
    historia: list[dict],
    pamiec_stala: list[str],
    sciezka_historii: Path = SCIEZKA_HISTORII,
    sciezka_pamieci_stalej: Path = SCIEZKA_PAMIECI_STALEJ,
    rag_memory: Any | None = None,
    assistant_state: Any | None = None,
    profile_store: Any | None = None,
    task_store: Any | None = None,
    project_store: Any | None = None,
    tts_client: Any | None = None,
) -> tuple[bool, list[dict], list[str]]:
    tekst = tekst_uzytkownika.strip().lower()

    if tekst == "/pomoc":
        pokaz_pomoc()
        print()
        return True, historia, pamiec_stala

    if tekst == "/status":
        status_mowy = "wlaczona" if czy_mowa_wlaczona() else "wylaczona"
        print(f"Historia rozmowy: {len(historia)} wiadomosci")
        print(f"Pamiec stala: {len(pamiec_stala)} wpisow")
        print(f"Odpowiedzi glosowe TTS: {status_mowy}")
        if assistant_state is not None:
            print(f"Tryb odpowiedzi: {assistant_state.get_response_mode()}")
            print(f"Aktywny projekt: {assistant_state.get_active_project() or 'brak'}")
        print()
        return True, historia, pamiec_stala

    if tekst == "/model":
        print(f"{NAZWA_ASYSTENTA}: Aktualny model LLM: {MODEL_LLM}")
        print()
        return True, historia, pamiec_stala

    if tekst.startswith("/voice"):
        _obsluz_komende_voice(tekst)
        return True, historia, pamiec_stala

    if tekst in {"/stop", "stop", "przerwij", "cisza"}:
        if tts_client is not None:
            tts_client.stop()
        print(f"{NAZWA_ASYSTENTA}: Przerywam odtwarzanie.")
        print()
        return True, historia, pamiec_stala

    if tekst.startswith("/debug"):
        _obsluz_komende_debug(tekst)
        return True, historia, pamiec_stala

    if tekst.startswith("/rag"):
        _obsluz_komende_rag(tekst, rag_memory)
        return True, historia, pamiec_stala

    if tekst.startswith("/mode"):
        _obsluz_komende_mode(tekst, assistant_state)
        return True, historia, pamiec_stala

    if tekst.startswith("/profile"):
        _obsluz_komende_profile(tekst_uzytkownika, profile_store)
        return True, historia, pamiec_stala

    if tekst.startswith("/task") or tekst.startswith("/zadanie"):
        _obsluz_komende_task(tekst_uzytkownika, task_store)
        return True, historia, pamiec_stala

    if tekst.startswith("/project") or tekst.startswith("/projekt"):
        _obsluz_komende_project(tekst_uzytkownika, assistant_state, project_store)
        return True, historia, pamiec_stala

    if tekst == "/briefing":
        if profile_store is None or task_store is None or project_store is None:
            print(f"{NAZWA_ASYSTENTA}: Briefing nie jest podlaczony w tej sesji.")
        else:
            active_project = (
                assistant_state.get_active_project() if assistant_state is not None else None
            )
            print(
                build_briefing(
                    profile_store=profile_store,
                    task_store=task_store,
                    project_store=project_store,
                    active_project=active_project,
                    memory_count=len(pamiec_stala),
                )
            )
        print()
        return True, historia, pamiec_stala

    if tekst_uzytkownika.lower().startswith("/zapamietaj"):
        tresc_do_zapamietania = tekst_uzytkownika[len("/zapamietaj") :].strip()

        if tresc_do_zapamietania == "":
            print(f"{NAZWA_ASYSTENTA}: Uzyj komendy: /zapamietaj twoja_tresc")
            print()
            return True, historia, pamiec_stala

        pamiec_stala = dodaj_do_pamieci_stalej(
            pamiec_stala,
            tresc_do_zapamietania,
        )
        zapisz_pamiec_stala(pamiec_stala, sciezka_pamieci_stalej)

        print(f"{NAZWA_ASYSTENTA}: Zapisalem to w pamieci stalej.")
        print()
        return True, historia, pamiec_stala

    if tekst == "/pamiec":
        print(formatuj_pamiec_stala(pamiec_stala))
        print()
        return True, historia, pamiec_stala

    if tekst == "/reset":
        historia = []
        wyczysc_historie(sciezka_historii)
        print(f"{NAZWA_ASYSTENTA}: Kontekst rozmowy zostal zresetowany.")
        print("Pamiec stala nie zostala naruszona.")
        print()
        return True, historia, pamiec_stala

    if tekst == "/wyczysc_pamiec":
        potwierdzenie = input(
            "Czy na pewno chcesz wyczyscic pamiec stala? (tak/nie): "
        ).strip().lower()

        if potwierdzenie == "tak":
            pamiec_stala = []
            wyczysc_pamiec_stala(sciezka_pamieci_stalej)
            print(f"{NAZWA_ASYSTENTA}: Pamiec stala zostala wyczyszczona.")
        else:
            print(f"{NAZWA_ASYSTENTA}: Anulowano czyszczenie pamieci stalej.")

        print()
        return True, historia, pamiec_stala

    if tekst == "/wyczysc_historie":
        potwierdzenie = input(
            "Czy na pewno chcesz wyczyscic historie rozmowy? (tak/nie): "
        ).strip().lower()

        if potwierdzenie == "tak":
            historia = []
            wyczysc_historie(sciezka_historii)
            print(f"{NAZWA_ASYSTENTA}: Historia rozmowy zostala wyczyszczona.")
        else:
            print(f"{NAZWA_ASYSTENTA}: Anulowano czyszczenie historii.")

        print()
        return True, historia, pamiec_stala

    return False, historia, pamiec_stala


def _obsluz_komende_voice(tekst: str) -> None:
    czesci = tekst.split()

    if len(czesci) == 1 or czesci[1] == "status":
        status = "wlaczona" if czy_mowa_wlaczona() else "wylaczona"
        print(f"{NAZWA_ASYSTENTA}: Mowa jest {status}.")
        print()
        return

    if czesci[1] == "on":
        ustaw_mowe(True)
        print(f"{NAZWA_ASYSTENTA}: Odpowiedzi glosowe zostaly wlaczone.")
        print()
        return

    if czesci[1] == "off":
        ustaw_mowe(False)
        print(f"{NAZWA_ASYSTENTA}: Odpowiedzi glosowe zostaly wylaczone.")
        print()
        return

    print(f"{NAZWA_ASYSTENTA}: Uzyj: /voice on, /voice off albo /voice status")
    print()


def _obsluz_komende_debug(tekst: str) -> None:
    czesci = tekst.split()

    if len(czesci) == 1 or czesci[1] == "status":
        status = "wlaczony" if czy_debug_wlaczony() else "wylaczony"
        print(f"{NAZWA_ASYSTENTA}: Tryb debugowania jest {status}.")
        print()
        return

    if czesci[1] == "on":
        ustaw_debug(True)
        print(f"{NAZWA_ASYSTENTA}: Tryb debugowania zostal wlaczony.")
        print()
        return

    if czesci[1] == "off":
        ustaw_debug(False)
        print(f"{NAZWA_ASYSTENTA}: Tryb debugowania zostal wylaczony.")
        print()
        return

    print(f"{NAZWA_ASYSTENTA}: Uzyj: /debug on, /debug off albo /debug status")
    print()


def _obsluz_komende_rag(tekst: str, rag_memory: Any | None) -> None:
    if rag_memory is None:
        print(f"{NAZWA_ASYSTENTA}: RAG nie jest podlaczony w tej sesji.")
        print()
        return

    if tekst in {"/rag", "/rag status"}:
        print(f"{NAZWA_ASYSTENTA}: {rag_memory.status()}")
        print()
        return

    if tekst == "/rag index":
        chunks_count = rag_memory.build_or_update_index()
        print(f"{NAZWA_ASYSTENTA}: Zindeksowalem {chunks_count} fragmentow dokumentow.")
        print()
        return

    print(f"{NAZWA_ASYSTENTA}: Uzyj: /rag status albo /rag index")
    print()


def _obsluz_komende_mode(tekst: str, assistant_state: Any | None) -> None:
    if assistant_state is None:
        print(f"{NAZWA_ASYSTENTA}: Tryby odpowiedzi nie sa podlaczone w tej sesji.")
        print()
        return

    parts = tekst.split(maxsplit=1)
    if len(parts) == 1 or parts[1] == "status":
        print(f"{NAZWA_ASYSTENTA}: Aktualny tryb: {assistant_state.get_response_mode()}")
        print(f"Dostepne tryby: {', '.join(list_modes())}")
        print()
        return

    mode = parts[1].strip().lower()
    if mode not in list_modes():
        print(f"{NAZWA_ASYSTENTA}: Nie znam trybu '{mode}'. Dostepne: {', '.join(list_modes())}")
        print()
        return

    assistant_state.set_response_mode(mode)
    print(f"{NAZWA_ASYSTENTA}: Tryb odpowiedzi ustawiony na {mode}.")
    print()


def _obsluz_komende_profile(tekst_uzytkownika: str, profile_store: Any | None) -> None:
    if profile_store is None:
        print(f"{NAZWA_ASYSTENTA}: Profil nie jest podlaczony w tej sesji.")
        print()
        return

    parts = tekst_uzytkownika.split(maxsplit=3)
    if len(parts) == 1:
        print(profile_store.format_for_terminal())
        print()
        return

    if len(parts) >= 4 and parts[1].lower() == "set":
        profile_store.set_value(parts[2], parts[3])
        print(f"{NAZWA_ASYSTENTA}: Zaktualizowalem profil.")
        print()
        return

    print(f"{NAZWA_ASYSTENTA}: Uzyj: /profile albo /profile set pole wartosc")
    print()


def _obsluz_komende_task(tekst_uzytkownika: str, task_store: Any | None) -> None:
    if task_store is None:
        print(f"{NAZWA_ASYSTENTA}: Zadania nie sa podlaczone w tej sesji.")
        print()
        return

    parts = tekst_uzytkownika.split(maxsplit=2)
    action = parts[1].lower() if len(parts) >= 2 else "list"

    if action in {"list", "pokaz"}:
        print(task_store.format())
        print()
        return

    if action in {"add", "dodaj"} and len(parts) == 3:
        task = task_store.add(parts[2])
        print(f"{NAZWA_ASYSTENTA}: Dodalem zadanie #{task['id']}.")
        print()
        return

    if action in {"done", "zrobione"} and len(parts) == 3:
        if task_store.mark_done(_parse_int(parts[2])):
            print(f"{NAZWA_ASYSTENTA}: Oznaczylem zadanie jako wykonane.")
        else:
            print(f"{NAZWA_ASYSTENTA}: Nie znalazlem takiego zadania.")
        print()
        return

    if action in {"remove", "usun"} and len(parts) == 3:
        if task_store.remove(_parse_int(parts[2])):
            print(f"{NAZWA_ASYSTENTA}: Usunalem zadanie.")
        else:
            print(f"{NAZWA_ASYSTENTA}: Nie znalazlem takiego zadania.")
        print()
        return

    print(f"{NAZWA_ASYSTENTA}: Uzyj: /task add tresc, /task list, /task done id")
    print()


def _obsluz_komende_project(
    tekst_uzytkownika: str,
    assistant_state: Any | None,
    project_store: Any | None,
) -> None:
    if assistant_state is None or project_store is None:
        print(f"{NAZWA_ASYSTENTA}: Projekty nie sa podlaczone w tej sesji.")
        print()
        return

    parts = tekst_uzytkownika.split(maxsplit=2)
    if len(parts) == 1 or parts[1].lower() == "status":
        print(project_store.summarize(assistant_state.get_active_project()))
        print()
        return

    action = parts[1].lower()
    if action in {"list", "lista"}:
        print(project_store.format_all())
        print()
        return

    if action in {"stop", "clear", "wyczysc"}:
        assistant_state.set_active_project(None)
        print(f"{NAZWA_ASYSTENTA}: Wylaczylem aktywny projekt.")
        print()
        return

    if action == "log" and len(parts) == 3:
        active_project = assistant_state.get_active_project()
        if not active_project:
            print(f"{NAZWA_ASYSTENTA}: Najpierw ustaw aktywny projekt: /project nazwa")
        else:
            project_store.add_note(active_project, parts[2])
            print(f"{NAZWA_ASYSTENTA}: Dopisalem notatke do projektu.")
        print()
        return

    project_name = " ".join(parts[1:]).strip()
    project_store.ensure_project(project_name)
    assistant_state.set_active_project(project_name)
    print(f"{NAZWA_ASYSTENTA}: Aktywny projekt ustawiony na {project_name}.")
    print()


def _parse_int(value: str) -> int:
    try:
        return int(value.strip())
    except ValueError:
        return -1
