from __future__ import annotations

import asyncio
import os
import threading
import time
from contextlib import asynccontextmanager
from contextlib import suppress

from fastapi import FastAPI, WebSocket, WebSocketDisconnect
from fastapi.responses import RedirectResponse, Response
from fastapi.staticfiles import StaticFiles

from src.app_launcher import close_app_window
from src.assistant_state import AssistantStatus
from src.config import PROJECT_ROOT, load_settings
from src.conversation_engine import ConversationEngine, ConversationEvent
from src.logger import configure_logging, get_logger
from src.long_term_memory import formatuj_memory_review
from src.long_term_memory import zapisz_pamiec_stala
from src.memory_store import zapisz_historie
from src.operational_briefing import build_operational_briefing
from src.startup_checks import read_startup_warnings
from src.intent_router import IntentType, classify_intent
from src.voice_commands import is_shutdown_command, is_tts_stop_command


settings = load_settings()
configure_logging(settings.log_level)
logger = get_logger(__name__)
engine = ConversationEngine(settings)
ui_dir = PROJECT_ROOT / "ui"
connected_websockets: set[WebSocket] = set()
pending_memory_candidates: dict[WebSocket, str] = {}
last_wake_transcript = ""
last_response = ""
recording_lock = asyncio.Lock()
auto_wake_task: asyncio.Task | None = None


@asynccontextmanager
async def lifespan(_app: FastAPI):
    global auto_wake_task
    if settings.input_mode == "wake":
        logger.info("Auto wake listener enabled. Wake phrase: %s", settings.wake_phrase)
        auto_wake_task = asyncio.create_task(_auto_wake_loop())

    try:
        yield
    finally:
        if auto_wake_task is not None:
            logger.info("Stopping auto wake listener.")
            auto_wake_task.cancel()
            with suppress(asyncio.CancelledError):
                await auto_wake_task


app = FastAPI(title="JARVIS Local UI", lifespan=lifespan)
app.mount("/ui", StaticFiles(directory=ui_dir), name="ui")


@app.get("/")
def index() -> RedirectResponse:
    return RedirectResponse("/ui/index.html")


@app.get("/favicon.ico", include_in_schema=False)
def favicon() -> Response:
    return Response(status_code=204)


@app.websocket("/api/ws")
async def websocket_endpoint(websocket: WebSocket) -> None:
    await websocket.accept()
    connected_websockets.add(websocket)
    await websocket.send_json({"state": "IDLE", "payload": "connected"})
    await websocket.send_json({"state": "DASHBOARD", "payload": build_dashboard_snapshot()})

    try:
        while True:
            message = await websocket.receive_json()
            message_type = str(message.get("type", "text"))

            if message_type == "stop":
                engine.stop_all()
                await websocket.send_json({"state": "IDLE", "payload": "stopped"})
                continue

            if message_type == "memory_decision":
                await _handle_memory_decision(websocket, message)
                continue

            if message_type == "clear_transcripts":
                await _clear_working_transcripts(websocket)
                continue

            if message_type == "history_toggle":
                engine.history_enabled = bool(message.get("enabled", True))
                await websocket.send_json({"state": "DASHBOARD", "payload": build_dashboard_snapshot()})
                continue

            if message_type == "listen":
                if settings.input_mode == "wake":
                    await _handle_wake_scan(websocket)
                    continue

                text, utterance_end_time = await _listen_once_for_command(websocket)
            else:
                text = str(message.get("payload", "")).strip()
                utterance_end_time = None
                if settings.input_mode == "wake" and text and not text.startswith("/"):
                    if await _handle_local_voice_command(text, websocket):
                        continue
                    text = _extract_command_after_wake_phrase(text)
                    if not text:
                        logger.info("Wake gate blocked UI text payload without activation phrase.")
                        await websocket.send_json(
                            {
                                "state": "SLEEPING",
                                "payload": f"Tryb wake: czekam na fraze {settings.wake_phrase}.",
                            }
                        )
                        continue
                    logger.info("Wake gate accepted UI text payload after activation phrase.")

            if not text:
                await websocket.send_json({"state": "IDLE", "payload": ""})
                continue

            if await _handle_local_voice_command(text, websocket):
                continue
            await _offer_memory_candidate(websocket, text)

            for event in engine.stream_response(text, utterance_end_time):
                await _send_event(websocket, event)
            await websocket.send_json({"state": "DASHBOARD", "payload": build_dashboard_snapshot()})
            await _settle_after_response(websocket, return_to_sleeping=False)
            await websocket.send_json({"state": "DASHBOARD", "payload": build_dashboard_snapshot()})

    except WebSocketDisconnect:
        engine.stop_all()
    finally:
        pending_memory_candidates.pop(websocket, None)
        connected_websockets.discard(websocket)


@app.post("/api/stop")
def stop_current_activity() -> dict[str, str]:
    engine.stop_all()
    return {"state": "IDLE", "payload": "stopped"}


@app.post("/api/recording/stop")
def stop_recording() -> dict[str, str]:
    engine.stop_recording()
    return {"state": "LISTENING", "payload": "recording stop requested"}


def serialize_event(event: ConversationEvent) -> dict[str, str]:
    return event.as_dict()


def build_dashboard_snapshot() -> dict:
    active_project = engine.assistant_state.get_active_project()
    route_decision = engine.last_route_decision
    briefing = build_operational_briefing(
        engine.assistant_state,
        engine.task_store,
        engine.project_store,
        engine.episodic_memory,
        engine.cost_tracker,
    )
    return {
        "status": engine.assistant_state.get_status(),
        "llm_gate": "blocked_until_wake" if settings.input_mode == "wake" else "active",
        "history_enabled": engine.history_enabled,
        "last_intent": route_decision.intent.value if route_decision else "none",
        "last_route": route_decision.route.value if route_decision else "none",
        "wake_detector": engine.wake_detector.status(),
        "cost": engine.cost_tracker.snapshot(),
        "briefing": briefing.format(),
        "episodic_memory": engine.episodic_memory.snapshot(),
        "last_wake_transcript": last_wake_transcript,
        "last_response": last_response,
        "tasks": engine.task_store.list(include_done=True)[:8],
        "active_project": active_project or "brak",
        "project_status": engine.project_store.summarize(active_project),
        "memory_review": formatuj_memory_review(engine.pamiec_stala),
        "rag_status": engine.rag_memory.status(),
        "setup_warnings": read_startup_warnings(),
    }


async def _auto_wake_loop() -> None:
    await asyncio.sleep(1.0)
    await _broadcast({"state": "SLEEPING", "payload": "Wake mode aktywny."})

    while True:
        await _handle_wake_scan()


async def _broadcast(message: dict[str, str]) -> None:
    stale_websockets = []
    for websocket in connected_websockets:
        try:
            await websocket.send_json(message)
        except RuntimeError:
            stale_websockets.append(websocket)

    for websocket in stale_websockets:
        connected_websockets.discard(websocket)


async def _handle_wake_scan(websocket: WebSocket | None = None) -> None:
    global last_wake_transcript
    await _send_or_broadcast(websocket, {"state": "SLEEPING", "payload": ""})
    async with recording_lock:
        wake_text = await asyncio.to_thread(
            engine.stt_client.listen_and_transcribe,
            settings.wake_record_seconds,
        )

    if not wake_text:
        await _send_or_broadcast(websocket, {"state": "SLEEPING", "payload": ""})
        return

    wake_text = engine.correct_transcript(wake_text, allow_llm=False)
    logger.info("Wake scan heard fragment: %s", wake_text)
    last_wake_transcript = wake_text
    await _send_or_broadcast(
        websocket,
        {
            "state": "LISTENING",
            "payload": f"Transkrypcja robocza: {wake_text}",
        },
    )

    if await _handle_local_voice_command(wake_text, websocket):
        return

    wake_detection = engine.wake_detector.detect_from_text(wake_text)
    if not wake_detection.activated:
        logger.info("Wake gate ignored fragment without activation phrase.")
        await _send_or_broadcast(
            websocket,
            {
                "state": "SLEEPING",
                "payload": f"Czekam na fraze: {settings.wake_phrase}",
            },
        )
        return

    logger.info("Wake phrase detected. Waiting for command.")
    await _send_or_broadcast(
        websocket,
        {
            "state": "WAKE_DETECTED",
            "payload": f"Aktywacja wykryta ({wake_detection.method}).",
        },
    )
    await asyncio.to_thread(engine.acknowledge_wake_detected)
    await _send_or_broadcast(
        websocket,
        {
            "state": "LISTENING_COMMAND",
            "payload": "Słucham.",
        },
    )
    command_text, utterance_end_time = await _listen_once_for_command(websocket)
    if not command_text:
        logger.info(
            "No command heard within %s seconds after activation.",
            settings.command_timeout_seconds,
        )
        command_text, utterance_end_time = await _ask_before_sleeping(websocket)
        if not command_text:
            await _send_or_broadcast(
                websocket,
                {
                    "state": "SLEEPING",
                    "payload": "Wracam do snu.",
                },
            )
            return

        logger.info(
            "Command heard during awake confirmation window. Length: %s",
            len(command_text),
        )

    await _run_awake_conversation(websocket, command_text, utterance_end_time)


async def _run_awake_conversation(
    websocket: WebSocket | None,
    command_text: str,
    utterance_end_time: float,
) -> None:
    while command_text:
        if await _handle_local_voice_command(command_text, websocket):
            return

        if websocket is not None:
            await _offer_memory_candidate(websocket, command_text)

        logger.info("Sending activated voice command to LLM. Length: %s", len(command_text))
        engine.assistant_state.set_status(AssistantStatus.ACTIVE_CONVERSATION)
        for event in engine.stream_response(command_text, utterance_end_time):
            await _send_event(websocket, event)

        await _send_or_broadcast(
            websocket,
            {"state": "DASHBOARD", "payload": build_dashboard_snapshot()},
        )
        await _settle_after_response(websocket, return_to_sleeping=False)
        await _send_or_broadcast(
            websocket,
            {"state": "DASHBOARD", "payload": build_dashboard_snapshot()},
        )

        logger.info(
            "Keeping JARVIS awake for follow-up command for %s seconds.",
            settings.follow_up_timeout_seconds,
        )
        engine.assistant_state.set_status(AssistantStatus.WAITING_FOLLOWUP)
        command_text, utterance_end_time = await _listen_once_for_command(
            websocket,
            max_seconds=settings.follow_up_timeout_seconds,
        )
        if command_text:
            continue

        command_text, utterance_end_time = await _ask_before_sleeping(websocket)
        if not command_text:
            engine.assistant_state.set_status(AssistantStatus.SLEEPING)
            await _send_or_broadcast(
                websocket,
                {
                    "state": "SLEEPING",
                    "payload": "Wracam do snu.",
                },
            )
            return


async def _listen_once_for_command(
    websocket: WebSocket | None = None,
    max_seconds: int | None = None,
) -> tuple[str, float]:
    await _send_or_broadcast(websocket, {"state": "LISTENING_COMMAND", "payload": ""})
    async with recording_lock:
        text, utterance_end_time = await asyncio.to_thread(
            engine.listen_for_command,
            max_seconds,
        )
    await _send_or_broadcast(websocket, {"state": "LISTENING_COMMAND", "payload": text})
    return text, utterance_end_time


async def _ask_before_sleeping(websocket: WebSocket | None = None) -> tuple[str, float]:
    prompt = "Mogę iść spać, szefie?"
    logger.info(
        "No command after wake phrase. Asking sleep confirmation and listening for %s seconds.",
        settings.awake_confirmation_timeout_seconds,
    )
    engine.assistant_state.set_status(AssistantStatus.GOING_SLEEP)
    await _send_or_broadcast(
        websocket,
        {
            "state": "GOING_SLEEP",
            "payload": prompt,
        },
    )
    await asyncio.to_thread(engine.tts_client.speak, prompt, True)
    return await _listen_once_for_command(
        websocket,
        max_seconds=settings.awake_confirmation_timeout_seconds,
    )


async def _send_or_broadcast(websocket: WebSocket | None, message: dict[str, str]) -> None:
    if websocket is None:
        await _broadcast(message)
        return
    await websocket.send_json(message)


async def _send_event(websocket: WebSocket | None, event: ConversationEvent) -> None:
    global last_response
    message = event.as_dict()
    if message["state"] == "IDLE" and message.get("payload"):
        last_response = message["payload"]
        if engine.tts_client.is_playing():
            message = {"state": "SPEAKING", "payload": message["payload"]}
    await _send_or_broadcast(websocket, message)


async def _settle_after_response(
    websocket: WebSocket | None,
    return_to_sleeping: bool,
) -> None:
    speech_was_playing = False

    while engine.tts_client.is_playing():
        speech_was_playing = True
        engine.assistant_state.set_status(AssistantStatus.SPEAKING)
        await _send_or_broadcast(websocket, {"state": "SPEAKING", "payload": ""})
        await asyncio.sleep(0.15)

    should_clear_response = settings.input_mode == "wake" and bool(last_response)
    clear_delay = max(0.0, settings.response_text_clear_delay_seconds)
    if should_clear_response:
        if clear_delay > 0:
            await asyncio.sleep(clear_delay)
        await _send_or_broadcast(websocket, {"state": "CLEAR_TRANSCRIPT", "payload": ""})

    if (
        speech_was_playing
        and return_to_sleeping
        and settings.post_speech_sleep_delay_seconds > clear_delay
    ):
        await asyncio.sleep(settings.post_speech_sleep_delay_seconds - clear_delay)

    final_status = AssistantStatus.SLEEPING if return_to_sleeping else AssistantStatus.IDLE
    engine.assistant_state.set_status(final_status)
    await _send_or_broadcast(
        websocket,
        {"state": final_status.value.upper(), "payload": ""},
    )


def _extract_command_after_wake_phrase(text: str) -> str:
    return engine.stt_client.extract_command_after_wake_phrase(text)


async def _handle_local_voice_command(text: str, websocket: WebSocket | None = None) -> bool:
    decision = classify_intent(text)
    engine.last_route_decision = decision

    if is_tts_stop_command(text):
        logger.info("Local voice command received: stop TTS.")
        engine.stop_audio()
        await _send_or_broadcast(
            websocket,
            {"state": "SLEEPING", "payload": "Przerywam odtwarzanie."},
        )
        return True

    if decision.intent == IntentType.SLEEP:
        logger.info("Local voice command received: sleep.")
        engine.assistant_state.set_status(AssistantStatus.SLEEPING)
        await _send_or_broadcast(
            websocket,
            {"state": "SLEEPING", "payload": "Przechodze w tryb czuwania."},
        )
        return True

    if decision.intent == IntentType.REPEAT:
        logger.info("Local voice command received: repeat last response.")
        payload = last_response or "Nie mam jeszcze czego powtorzyc."
        if last_response:
            await asyncio.to_thread(engine.tts_client.speak, last_response, False)
        await _send_or_broadcast(websocket, {"state": "SPEAKING", "payload": payload})
        return True

    if decision.intent in {IntentType.STATUS, IntentType.PROJECT_STATUS}:
        logger.info("Local voice command received: status.")
        briefing = build_operational_briefing(
            engine.assistant_state,
            engine.task_store,
            engine.project_store,
            engine.episodic_memory,
            engine.cost_tracker,
        )
        await _send_or_broadcast(websocket, {"state": "IDLE", "payload": briefing.format()})
        await _send_or_broadcast(websocket, {"state": "DASHBOARD", "payload": build_dashboard_snapshot()})
        return True

    if decision.intent in {IntentType.VOLUME_DOWN, IntentType.VOLUME_UP}:
        await _send_or_broadcast(
            websocket,
            {
                "state": "IDLE",
                "payload": "Rozpoznalem intencje zmiany glosnosci; sterowanie mikserem dodamy jako osobne narzedzie.",
            },
        )
        return True

    if is_shutdown_command(text):
        logger.info("Local voice command received: shutdown.")
        engine.stop_all()
        zapisz_historie(engine.historia, settings.history_path)
        zapisz_pamiec_stala(engine.pamiec_stala, settings.long_term_memory_path)
        await _send_or_broadcast(
            websocket,
            {"state": "SHUTDOWN", "payload": "Wylaczam JARVISA."},
        )
        _shutdown_process_soon()
        return True

    return False


def _shutdown_process_soon(delay_seconds: float = 0.6) -> None:
    def shutdown() -> None:
        time.sleep(delay_seconds)
        close_app_window()
        os._exit(0)

    threading.Thread(target=shutdown, daemon=True).start()


async def _offer_memory_candidate(websocket: WebSocket, text: str) -> None:
    candidate = engine.get_memory_candidate(text)
    if not candidate:
        return
    pending_memory_candidates[websocket] = candidate
    await websocket.send_json(
        {
            "state": "MEMORY_CANDIDATE",
            "payload": f"Wykrylem fakt do pamieci: {candidate}",
        }
    )


async def _handle_memory_decision(websocket: WebSocket, message: dict) -> None:
    candidate = pending_memory_candidates.pop(websocket, None)
    if not candidate:
        await websocket.send_json(
            {"state": "IDLE", "payload": "Brak oczekujacego faktu do pamieci."}
        )
        return

    decision = str(message.get("decision", "")).strip().lower()
    if decision == "save":
        saved = engine.save_memory_candidate(candidate)
        payload = "Zapisalem fakt w pamieci stalej." if saved else "Ten fakt byl juz zapisany."
    else:
        payload = "Nie zapisuje tego faktu."

    await websocket.send_json({"state": "IDLE", "payload": payload})
    await websocket.send_json({"state": "DASHBOARD", "payload": build_dashboard_snapshot()})


async def _clear_working_transcripts(websocket: WebSocket) -> None:
    global last_wake_transcript, last_response
    last_wake_transcript = ""
    last_response = ""
    await websocket.send_json({"state": "IDLE", "payload": "Wyczyszczono transkrypcje robocze."})
    await websocket.send_json({"state": "DASHBOARD", "payload": build_dashboard_snapshot()})
