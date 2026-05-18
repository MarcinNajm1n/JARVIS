from __future__ import annotations

from pathlib import Path

from config import NAZWA_ASYSTENTA
from src.assistant_state import AssistantStateStore, AssistantStatus
from src.auto_memory import extract_memory_candidate
from src.command_handler import obsluz_komende
from src.config import load_settings
from src.llm import LLMClient, Message
from src.logger import configure_logging
from src.long_term_memory import wczytaj_pamiec_stala, zapisz_pamiec_stala
from src.memory_store import wczytaj_historie, zapisz_historie
from src.profile_store import UserProfileStore
from src.project_store import ProjectStore
from src.rag import RAGMemory
from src.response_modes import get_mode_instruction
from src.stt import SpeechToTextClient
from src.task_store import TaskStore
from src.terminal_ui import TerminalUI
from src.tts import TextToSpeechClient
from src.voice_state import czy_mowa_wlaczona


def uruchom_petle_rozmowy() -> None:
    settings = load_settings()
    configure_logging(settings.log_level)

    llm_client = LLMClient(settings)
    stt_client = SpeechToTextClient(settings)
    tts_client = TextToSpeechClient(settings)
    rag_memory = RAGMemory(settings)
    rag_memory.ensure_index()
    assistant_state = AssistantStateStore(settings)
    profile_store = UserProfileStore(settings)
    task_store = TaskStore(settings)
    project_store = ProjectStore(settings)
    ui = TerminalUI(settings)

    historia: list[Message] = wczytaj_historie(settings.history_path)
    pamiec_stala = wczytaj_pamiec_stala(settings.long_term_memory_path)
    input_mode = settings.input_mode

    _print_startup(input_mode, len(historia), len(pamiec_stala))

    try:
        while True:
            assistant_state.set_status(
                AssistantStatus.SLEEPING if input_mode == "wake" else AssistantStatus.IDLE
            )
            ui.status(AssistantStatus.SLEEPING if input_mode == "wake" else AssistantStatus.IDLE)
            tekst_uzytkownika, input_mode = _pobierz_wejscie(
                input_mode,
                stt_client,
                ui,
                assistant_state,
            )
            tekst_uzytkownika = tekst_uzytkownika.strip()

            if not tekst_uzytkownika:
                continue

            if tekst_uzytkownika.lower() in {"exit", "quit", "/exit", "/quit"}:
                zapisz_historie(historia, settings.history_path)
                zapisz_pamiec_stala(pamiec_stala, settings.long_term_memory_path)
                print(f"{NAZWA_ASYSTENTA}: Zapisalem dane i koncze dzialanie.")
                break

            nowy_tryb = _obsluz_lokalna_komende_input_mode(tekst_uzytkownika, input_mode)
            if nowy_tryb != input_mode:
                input_mode = nowy_tryb
                continue

            czy_komenda, historia, pamiec_stala = obsluz_komende(
                tekst_uzytkownika,
                historia,
                pamiec_stala,
                sciezka_historii=settings.history_path,
                sciezka_pamieci_stalej=settings.long_term_memory_path,
                rag_memory=rag_memory,
                assistant_state=assistant_state,
                profile_store=profile_store,
                task_store=task_store,
                project_store=project_store,
                tts_client=tts_client,
            )
            if czy_komenda:
                continue

            pamiec_stala = _obsluz_pamiec_automatyczna(
                tekst_uzytkownika,
                pamiec_stala,
                settings.long_term_memory_path,
                settings.auto_memory_enabled,
            )

            historia.append({"role": "user", "content": tekst_uzytkownika})
            assistant_state.set_status(AssistantStatus.THINKING)
            ui.status(AssistantStatus.THINKING)
            rag_context = rag_memory.retrieve_context(tekst_uzytkownika)
            active_project = assistant_state.get_active_project()
            odpowiedz = llm_client.generate_response(
                history=historia,
                long_term_memory=pamiec_stala,
                rag_context=rag_context,
                user_profile=profile_store.format_for_prompt(),
                response_mode_instruction=get_mode_instruction(
                    assistant_state.get_response_mode()
                ),
                project_context=project_store.summarize(active_project),
            )
            historia.append({"role": "assistant", "content": odpowiedz})
            zapisz_historie(historia, settings.history_path)

            print(f"{NAZWA_ASYSTENTA}: {odpowiedz}")

            if czy_mowa_wlaczona() and not odpowiedz.startswith("Wystapil blad"):
                assistant_state.set_status(AssistantStatus.SPEAKING)
                ui.status(AssistantStatus.SPEAKING)
                tts_client.speak(odpowiedz)

            print()
    except KeyboardInterrupt:
        zapisz_historie(historia, settings.history_path)
        zapisz_pamiec_stala(pamiec_stala, settings.long_term_memory_path)
        print(f"\n{NAZWA_ASYSTENTA}: Przerwano. Zapisalem dane.")


def _print_startup(input_mode: str, history_count: int, memory_count: int) -> None:
    print(f"{NAZWA_ASYSTENTA} startuje...")
    print("Zakres MVP: rozmowa, pamiec lokalna, RAG, STT i TTS.")
    print("Wpisz '/pomoc', aby zobaczyc komendy. Wpisz 'exit', aby zakonczyc.")
    print(f"Aktualny tryb wejscia: {input_mode}.")
    print("Tryb wake nasluchuje frazy aktywacyjnej: 'jarvis aktywacja'.\n")

    if history_count:
        print(f"{NAZWA_ASYSTENTA}: Wczytalem historie rozmowy: {history_count} wiadomosci.")
    if memory_count:
        print(f"{NAZWA_ASYSTENTA}: Wczytalem pamiec stala: {memory_count} wpisow.")
    if history_count or memory_count:
        print()


def _pobierz_wejscie(
    input_mode: str,
    stt_client: SpeechToTextClient,
    ui: TerminalUI,
    assistant_state: AssistantStateStore,
) -> tuple[str, str]:
    if input_mode == "voice":
        decyzja = input("Ty [Enter=nagraj, tekst=napisz, /input text=klawiatura]: ").strip()
        if decyzja:
            return decyzja, input_mode

        print("Nagrywam. Mow naturalnie, zakoncze po chwili ciszy...")
        assistant_state.set_status(AssistantStatus.LISTENING)
        ui.status(AssistantStatus.LISTENING)
        transkrypcja = stt_client.listen_and_transcribe()
        if transkrypcja:
            print(f"Ty (STT): {transkrypcja}")
            return transkrypcja, input_mode

        print("Nie wykrylem wyraznej mowy. Sprobuj ponownie albo wpisz /input text.\n")
        return "", input_mode

    if input_mode == "wake":
        print(
            f"Nasluchuje frazy '{stt_client.settings.wake_phrase}'. "
            "Powiedz ja, a potem polecenie. Ctrl+C konczy program."
        )

        while True:
            assistant_state.set_status(AssistantStatus.SLEEPING)
            ui.status(AssistantStatus.SLEEPING)
            transkrypcja = stt_client.listen_and_transcribe(
                max_seconds=stt_client.settings.wake_record_seconds
            )
            if not transkrypcja:
                continue

            if stt_client.contains_wake_phrase(transkrypcja):
                print(f"{NAZWA_ASYSTENTA}: Aktywacja wykryta. Slucham polecenia...")
                assistant_state.set_status(AssistantStatus.LISTENING)
                ui.status(AssistantStatus.LISTENING)
                polecenie = stt_client.listen_and_transcribe()
                if polecenie:
                    print(f"Ty (STT): {polecenie}")
                    return polecenie, input_mode

                print(f"{NAZWA_ASYSTENTA}: Nie uslyszalem polecenia po aktywacji.\n")
                return "", input_mode

    return input("Ty: "), input_mode


def _obsluz_pamiec_automatyczna(
    tekst_uzytkownika: str,
    pamiec_stala: list[str],
    sciezka_pamieci: Path,
    auto_memory_enabled: bool,
) -> list[str]:
    if not auto_memory_enabled:
        return pamiec_stala

    kandydat = extract_memory_candidate(tekst_uzytkownika)
    if not kandydat or kandydat in pamiec_stala:
        return pamiec_stala

    decyzja = input(
        f"{NAZWA_ASYSTENTA}: Wykrylem potencjalny fakt do pamieci: "
        f"'{kandydat}'. Zapisac? (tak/nie): "
    ).strip().lower()

    if decyzja == "tak":
        pamiec_stala.append(kandydat)
        zapisz_pamiec_stala(pamiec_stala, sciezka_pamieci)
        print(f"{NAZWA_ASYSTENTA}: Zapisalem to w pamieci stalej.")

    return pamiec_stala


def _obsluz_lokalna_komende_input_mode(tekst: str, input_mode: str) -> str:
    tekst = tekst.strip().lower()

    if tekst in {"/input text", "/tryb tekst", "/tekst"}:
        print(f"{NAZWA_ASYSTENTA}: Tryb wejscia ustawiony na tekst.\n")
        return "text"

    if tekst in {"/input voice", "/tryb glos", "/glos"}:
        print(f"{NAZWA_ASYSTENTA}: Tryb wejscia ustawiony na mikrofon.\n")
        return "voice"

    if tekst in {"/input wake", "/wake", "/aktywacja"}:
        print(f"{NAZWA_ASYSTENTA}: Tryb aktywacji fraza zostal wlaczony.\n")
        return "wake"

    return input_mode
