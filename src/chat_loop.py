from __future__ import annotations

from pathlib import Path

from config import NAZWA_ASYSTENTA
from src.assistant_state import AssistantStatus
from src.config import load_settings
from src.conversation_engine import ConversationEngine
from src.logger import configure_logging, get_logger
from src.long_term_memory import zapisz_pamiec_stala
from src.memory_store import zapisz_historie
from src.terminal_ui import TerminalUI
from src.voice_commands import is_shutdown_command, is_tts_stop_command


def uruchom_petle_rozmowy() -> None:
    settings = load_settings()
    configure_logging(settings.log_level)
    engine = ConversationEngine(settings)
    ui = TerminalUI(settings)

    input_mode = settings.input_mode

    _print_startup(input_mode, len(engine.historia), len(engine.pamiec_stala))

    try:
        while True:
            engine.assistant_state.set_status(
                AssistantStatus.SLEEPING if input_mode == "wake" else AssistantStatus.IDLE
            )
            ui.status(AssistantStatus.SLEEPING if input_mode == "wake" else AssistantStatus.IDLE)
            tekst_uzytkownika, input_mode = _pobierz_wejscie(
                input_mode,
                engine,
                ui,
            )
            tekst_uzytkownika = tekst_uzytkownika.strip()

            if not tekst_uzytkownika:
                continue

            if tekst_uzytkownika.lower() in {"exit", "quit", "/exit", "/quit"} or is_shutdown_command(tekst_uzytkownika):
                zapisz_historie(engine.historia, settings.history_path)
                zapisz_pamiec_stala(engine.pamiec_stala, settings.long_term_memory_path)
                print(f"{NAZWA_ASYSTENTA}: Zapisalem dane i koncze dzialanie.")
                break

            nowy_tryb = _obsluz_lokalna_komende_input_mode(tekst_uzytkownika, input_mode)
            if nowy_tryb != input_mode:
                input_mode = nowy_tryb
                continue

            if settings.low_latency_mode and settings.streaming_llm:
                print(f"{NAZWA_ASYSTENTA}: ", end="", flush=True)
                printed_anything = False
                for event in engine.stream_response(tekst_uzytkownika):
                    if event.state == AssistantStatus.THINKING.value.upper() and event.payload:
                        printed_anything = True
                        print(event.payload, end="", flush=True)
                    elif event.state == AssistantStatus.SPEAKING.value.upper():
                        ui.status(AssistantStatus.SPEAKING)
                    elif event.state == AssistantStatus.IDLE.value.upper() and not printed_anything:
                        print(event.payload, end="", flush=True)
                print()
            else:
                ui.status(AssistantStatus.THINKING)
                odpowiedz = engine.generate_response(tekst_uzytkownika)
                print(f"{NAZWA_ASYSTENTA}: {odpowiedz}")

            print()
    except KeyboardInterrupt:
        zapisz_historie(engine.historia, settings.history_path)
        zapisz_pamiec_stala(engine.pamiec_stala, settings.long_term_memory_path)
        print(f"\n{NAZWA_ASYSTENTA}: Przerwano. Zapisalem dane.")


def _print_startup(input_mode: str, history_count: int, memory_count: int) -> None:
    print(f"{NAZWA_ASYSTENTA} startuje...")
    print("Zakres MVP: rozmowa, pamiec lokalna, RAG, STT i TTS.")
    print("Wpisz '/pomoc', aby zobaczyc komendy. Wpisz 'exit', aby zakonczyc.")
    print(f"Aktualny tryb wejscia: {input_mode}.")
    print("Tryb wake nasluchuje frazy aktywacyjnej: 'jarvis śpisz?'.\n")

    if history_count:
        print(f"{NAZWA_ASYSTENTA}: Wczytalem historie rozmowy: {history_count} wiadomosci.")
    if memory_count:
        print(f"{NAZWA_ASYSTENTA}: Wczytalem pamiec stala: {memory_count} wpisow.")
    if history_count or memory_count:
        print()


def _pobierz_wejscie(
    input_mode: str,
    engine: ConversationEngine,
    ui: TerminalUI,
) -> tuple[str, str]:
    stt_client = engine.stt_client
    assistant_state = engine.assistant_state

    if input_mode == "voice":
        decyzja = input("Ty [Enter=nagraj, tekst=napisz, /input text=klawiatura]: ").strip()
        if decyzja:
            return decyzja, input_mode

        print("Nagrywam. Mow naturalnie, zakoncze po chwili ciszy...")
        assistant_state.set_status(AssistantStatus.LISTENING)
        ui.status(AssistantStatus.LISTENING)
        transkrypcja, _utterance_end_time = engine.listen_once()
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

            get_logger(__name__).info("Wake scan heard fragment: %s", transkrypcja)
            if is_shutdown_command(transkrypcja) or is_tts_stop_command(transkrypcja):
                return transkrypcja, input_mode

            if stt_client.contains_wake_phrase(transkrypcja):
                get_logger(__name__).info("Wake phrase detected. Waiting for command.")
                print(f"{NAZWA_ASYSTENTA}: Aktywacja wykryta.")
                assistant_state.set_status(AssistantStatus.WAKE_DETECTED)
                ui.status(AssistantStatus.WAKE_DETECTED)
                engine.acknowledge_wake_detected()
                print(f"{NAZWA_ASYSTENTA}: Słucham.")
                assistant_state.set_status(AssistantStatus.LISTENING_COMMAND)
                ui.status(AssistantStatus.LISTENING_COMMAND)
                polecenie, _utterance_end_time = engine.listen_for_command()
                if polecenie:
                    print(f"Ty (STT): {polecenie}")
                    return polecenie, input_mode

                assistant_state.set_status(AssistantStatus.AWAKE_CONFIRM)
                ui.status(AssistantStatus.AWAKE_CONFIRM)
                prompt = "Mogę iść spać, szefie?"
                print(f"{NAZWA_ASYSTENTA}: {prompt}")
                engine.tts_client.speak(prompt, blocking=True)
                polecenie, _utterance_end_time = engine.listen_for_command(
                    max_seconds=stt_client.settings.awake_confirmation_timeout_seconds
                )
                if polecenie:
                    print(f"Ty (STT): {polecenie}")
                    return polecenie, input_mode

                print(f"{NAZWA_ASYSTENTA}: Wracam do snu.\n")
                return "", input_mode

    return input("Ty: "), input_mode


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
