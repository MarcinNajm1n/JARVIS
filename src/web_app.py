from __future__ import annotations

import asyncio
import ipaddress
import json
import os
import socket
import threading
import time
from contextlib import asynccontextmanager
from contextlib import suppress
from pathlib import Path
from urllib.parse import urlparse

import httpx
from fastapi import FastAPI, WebSocket, WebSocketDisconnect
from fastapi.responses import JSONResponse, RedirectResponse, Response
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
from src.display import build_display_payload
from src.graphify_cli import GraphifyParseError, build_local_graph
from src.retrieval import (
    RetrievalManager,
    RetrievalResult,
    build_realtime_llm_prompt,
    parse_jarvis_answer,
)
from src.visual_planner import plan_visual_result
from src.voice_commands import is_shutdown_command, is_tts_stop_command
from src.weather_service import extract_weather_location, get_current_weather


settings = load_settings()
configure_logging(settings.log_level)
logger = get_logger(__name__)
engine = ConversationEngine(settings)
retrieval_manager = RetrievalManager(settings)
ui_dir = PROJECT_ROOT / "ui"
connected_websockets: set[WebSocket] = set()
pending_memory_candidates: dict[WebSocket, str] = {}
last_wake_transcript = ""
last_response = ""
visual_result_history: list[dict] = []
recording_lock = asyncio.Lock()
auto_wake_task: asyncio.Task | None = None
IMAGE_PROXY_TIMEOUT_SECONDS = 8.0
IMAGE_PROXY_MAX_BYTES = 5 * 1024 * 1024


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


@app.get("/api/image-proxy")
async def image_proxy(url: str) -> Response:
    if not _is_safe_remote_image_url(url):
        logger.warning("Image proxy rejected unsafe URL: %s", _safe_url_for_log(url))
        return Response("Invalid image URL", status_code=400)
    try:
        async with httpx.AsyncClient(
            timeout=IMAGE_PROXY_TIMEOUT_SECONDS,
            follow_redirects=False,
            headers={"User-Agent": "JarvisImageProxy/1.0"},
        ) as client:
            response = await client.get(url)
    except httpx.HTTPError as error:
        logger.warning("Image proxy fetch failed url=%s error=%s", _safe_url_for_log(url), error)
        return Response("Image fetch failed", status_code=502)

    content_type = response.headers.get("content-type", "").split(";", 1)[0].strip().lower()
    content_length = 0
    with suppress(ValueError):
        content_length = int(response.headers.get("content-length") or 0)
    if 300 <= response.status_code < 400:
        logger.warning("Image proxy rejected upstream redirect for %s", _safe_url_for_log(url))
        return Response("Image redirects are not allowed", status_code=502)
    if response.status_code >= 400:
        logger.warning("Image proxy upstream returned %s for %s", response.status_code, _safe_url_for_log(url))
        return Response("Image fetch failed", status_code=502)
    if content_length > IMAGE_PROXY_MAX_BYTES or len(response.content) > IMAGE_PROXY_MAX_BYTES:
        logger.warning("Image proxy rejected oversized image: %s", _safe_url_for_log(url))
        return Response("Image too large", status_code=502)
    if not content_type.startswith("image/"):
        logger.warning("Image proxy rejected non-image content-type=%s url=%s", content_type, _safe_url_for_log(url))
        return Response("Upstream content is not an image", status_code=502)
    return Response(
        response.content,
        media_type=content_type,
        headers={"Cache-Control": "public, max-age=86400"},
    )


def _is_safe_remote_image_url(url: str) -> bool:
    try:
        parsed = urlparse(url)
    except ValueError:
        return False
    if parsed.scheme not in {"http", "https"} or not parsed.hostname:
        return False
    host = parsed.hostname.strip().lower()
    if host in {"localhost", "0.0.0.0"} or host.endswith(".localhost"):
        return False
    if _is_blocked_ip(host):
        return False
    try:
        resolved = socket.getaddrinfo(host, parsed.port or (443 if parsed.scheme == "https" else 80), type=socket.SOCK_STREAM)
    except socket.gaierror:
        return False
    return all(not _is_blocked_ip(address[4][0]) for address in resolved)


def _is_blocked_ip(value: str) -> bool:
    try:
        ip = ipaddress.ip_address(value)
    except ValueError:
        return False
    return (
        ip.is_private
        or ip.is_loopback
        or ip.is_link_local
        or ip.is_multicast
        or ip.is_reserved
        or ip.is_unspecified
    )


def _safe_url_for_log(url: str) -> str:
    try:
        parsed = urlparse(url)
    except ValueError:
        return "<invalid-url>"
    host = parsed.hostname or "<missing-host>"
    return f"{parsed.scheme}://{host}{parsed.path}"


@app.get("/api/graph")
def get_graph() -> JSONResponse:
    graph_path = PROJECT_ROOT / "graphify-out" / "local_graph.json"
    if not graph_path.exists():
        graph_path = PROJECT_ROOT / "graphify-out" / "graph.json"
    if not graph_path.exists():
        return JSONResponse(
            {
                "type": "visual_result",
                "mode": "graph",
                "ok": False,
                "title": "Graph unavailable",
                "summary": "No graph file found. Run graphify . first.",
                "nodes": [],
                "edges": [],
                "error": "EmptySearchResultError",
            },
            status_code=404,
        )
    return JSONResponse(json.loads(graph_path.read_text(encoding="utf-8")))


@app.post("/api/graphify")
async def run_graphify_api() -> dict:
    payload = await _build_graphify_payload(".")
    await _broadcast({"state": "GRAPH_READY", "payload": payload})
    return payload


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

            if await _handle_graphify_command(text, websocket):
                continue
            if await _handle_local_voice_command(text, websocket):
                continue
            if await _handle_visual_query(text, websocket):
                continue
            await _offer_memory_candidate(websocket, text)

            llm_text, retrieval_result = await _prepare_llm_text(websocket, text)
            if isinstance(retrieval_result, RetrievalResult):
                response_text = await _generate_realtime_response(
                    websocket,
                    text,
                    llm_text,
                    retrieval_result,
                )
            else:
                response_text = await _stream_engine_response(websocket, llm_text, utterance_end_time)
                await _send_planned_visual_result(websocket, text, response_text)
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


@app.post("/api/emergency-stop")
async def emergency_stop() -> dict[str, str]:
    engine.stop_all()
    engine.assistant_state.set_status(AssistantStatus.SLEEPING)
    await _broadcast({"state": "EMERGENCY_STOP", "payload": "Awaryjne zatrzymanie."})
    return {"state": "EMERGENCY_STOP", "payload": "stopped"}


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
        "visual_results": visual_result_history[-5:],
        "tasks": engine.task_store.list(include_done=True)[:8],
        "active_project": active_project or "brak",
        "project_status": engine.project_store.summarize(active_project),
        "memory_review": formatuj_memory_review(engine.pamiec_stala),
        "rag_status": engine.rag_memory.status(),
        "setup_warnings": read_startup_warnings(),
        "hud_animations_enabled": settings.jarvis_hud_animations_enabled,
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
        if await _handle_visual_query(command_text, websocket):
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
            continue

        if websocket is not None:
            await _offer_memory_candidate(websocket, command_text)

        logger.info("Sending activated voice command to LLM. Length: %s", len(command_text))
        engine.assistant_state.set_status(AssistantStatus.ACTIVE_CONVERSATION)
        llm_text, retrieval_result = await _prepare_llm_text(websocket, command_text)
        if isinstance(retrieval_result, RetrievalResult):
            response_text = await _generate_realtime_response(
                websocket,
                command_text,
                llm_text,
                retrieval_result,
            )
        else:
            response_text = await _stream_engine_response(websocket, llm_text, utterance_end_time)
            await _send_planned_visual_result(websocket, command_text, response_text)

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


async def _send_ui_event(websocket: WebSocket | None, text: str) -> None:
    await _send_or_broadcast(websocket, {"state": "UI_EVENT", "payload": text})


async def _prepare_llm_text(websocket: WebSocket | None, text: str):
    plan = retrieval_manager.router.plan(text)
    if not plan.needs_realtime or not settings.jarvis_enable_realtime_search:
        return text, None

    engine.assistant_state.set_status(AssistantStatus.SEARCHING)
    await _send_or_broadcast(websocket, {"state": "SEARCHING", "payload": "Skanuje aktualne zrodla."})
    await _send_ui_event(websocket, "classifying query")
    result = await asyncio.to_thread(retrieval_manager.retrieve, text)
    for operation in result.operations:
        detail = f": {operation.detail}" if operation.detail else ""
        await _send_ui_event(websocket, f"{operation.name.lower()}{detail}")
    if not result.has_evidence:
        await _send_ui_event(websocket, "insufficient evidence")
        return build_realtime_llm_prompt(text, result), result

    await _send_ui_event(websocket, f"evidence ready: {len(result.evidence)} chunks")
    return build_realtime_llm_prompt(text, result), result


async def _handle_visual_query(text: str, websocket: WebSocket | None = None) -> bool:
    global last_response
    decision = classify_intent(text)
    engine.last_route_decision = decision
    if decision.intent != IntentType.WEATHER_QUERY:
        return False

    location = extract_weather_location(text) or "Berlin"
    logger.info("Visual weather query detected. location=%s", location)
    engine.assistant_state.set_status(AssistantStatus.SEARCHING)
    await _send_or_broadcast(websocket, {"state": "SEARCHING", "payload": "Rozpoznano pytanie pogodowe."})
    await _send_ui_event(websocket, "rozpoznano pytanie")
    await _send_ui_event(websocket, f"wyszukuje {location}")

    result = await asyncio.to_thread(get_current_weather, location)
    payload = result.to_visual_payload()
    visual_result_history.append(payload)
    del visual_result_history[:-8]

    if result.ok:
        await _send_ui_event(websocket, "pobrano pogode")
    else:
        await _send_ui_event(websocket, "brak aktualnych danych pogodowych")

    engine.assistant_state.set_status(AssistantStatus.DISPLAYING_RESULT)
    await _send_or_broadcast(websocket, {"state": "DISPLAYING_RESULT", "payload": payload["message"]})
    await _send_or_broadcast(websocket, {"state": "VISUAL_RESULT", "payload": payload})
    await _send_ui_event(websocket, "gotowe")
    last_response = payload["message"]
    if result.ok:
        await asyncio.to_thread(engine.tts_client.speak, payload["message"], False)
    await _send_or_broadcast(websocket, {"state": "DASHBOARD", "payload": build_dashboard_snapshot()})
    return True


async def _stream_engine_response(
    websocket: WebSocket | None,
    text: str,
    utterance_end_time: float | None,
    speak: bool = True,
) -> str:
    response_text = ""
    try:
        events = engine.stream_response(text, utterance_end_time, speak=speak)
    except TypeError:
        events = engine.stream_response(text, utterance_end_time)
    for event in events:
        message = event.as_dict()
        if message["state"] == "IDLE" and message.get("payload"):
            response_text = str(message["payload"])
        await _send_event(websocket, event)
    return response_text or last_response


async def _generate_realtime_response(
    websocket: WebSocket | None,
    question: str,
    prompt_text: str,
    retrieval_result: RetrievalResult,
) -> str:
    global last_response
    engine.assistant_state.set_status(AssistantStatus.THINKING)
    await _send_or_broadcast(websocket, {"state": "THINKING", "payload": ""})
    await _send_ui_event(websocket, "generating answer")

    if retrieval_result.has_evidence:
        raw_response = await asyncio.to_thread(
            engine.generate_realtime_response,
            question,
            prompt_text,
        )
        jarvis_answer = parse_jarvis_answer(raw_response, retrieval_result)
    else:
        jarvis_answer = retrieval_result.fallback_answer()

    operations = list(jarvis_answer.operations)
    if not any(operation.get("name") == "SYNTHESIZING" for operation in operations):
        operations.append({"name": "SYNTHESIZING", "status": "done", "duration_ms": 0})
    if not any(operation.get("name") == "SPEAKING" for operation in operations):
        operations.append({"name": "SPEAKING", "status": "done", "duration_ms": 0})
    jarvis_answer = jarvis_answer.model_copy(update={"operations": operations})

    payload = build_display_payload(jarvis_answer, question)
    if retrieval_result.used_fallback:
        payload["fallback_notice"] = "PRIMARY SEARCH DEGRADED -> FALLBACK BRAVE ENGAGED"

    visual_result_history.append(payload)
    del visual_result_history[:-8]
    last_response = jarvis_answer.answer
    engine.assistant_state.set_status(AssistantStatus.DISPLAYING_RESULT)
    await _send_or_broadcast(websocket, {"state": "VISUAL_RESULT", "payload": payload})
    await _send_or_broadcast(websocket, {"state": "IDLE", "payload": jarvis_answer.answer})

    spoken_answer = jarvis_answer.spoken_answer.strip()
    if spoken_answer:
        engine.assistant_state.set_status(AssistantStatus.SPEAKING)
        await _send_or_broadcast(websocket, {"state": "SPEAKING", "payload": ""})
        await asyncio.to_thread(engine.tts_client.speak, spoken_answer, False)
    return jarvis_answer.answer


async def _send_planned_visual_result(
    websocket: WebSocket | None,
    question: str,
    answer: str,
    search_bundle=None,
) -> bool:
    if not question or not answer:
        return False

    engine.assistant_state.set_status(AssistantStatus.SEARCHING)
    await _send_or_broadcast(websocket, {"state": "SEARCHING", "payload": "Buduje display wyniku."})
    await _send_ui_event(websocket, "wyszukuje kontekst w sieci")
    if search_bundle is None:
        payload = await asyncio.to_thread(plan_visual_result, question, answer)
    else:
        payload = await asyncio.to_thread(
            plan_visual_result,
            question,
            answer,
            None,
            None,
            search_bundle,
        )
    if not payload:
        return False

    trace = payload.get("planner_trace") or {}
    logger.info(
        (
            "Visual planner generated display. mode=%s subject=%s source=%s "
            "confidence=%s search_query=%s validation=%s candidates=%s"
        ),
        payload.get("mode"),
        payload.get("subject") or payload.get("title"),
        trace.get("selection_source"),
        trace.get("confidence"),
        trace.get("search_query"),
        trace.get("validation"),
        trace.get("candidate_subjects"),
    )
    visual_result_history.append(payload)
    del visual_result_history[:-8]
    engine.assistant_state.set_status(AssistantStatus.DISPLAYING_RESULT)
    await _send_ui_event(websocket, "zbudowano display")
    await _send_or_broadcast(websocket, {"state": "VISUAL_RESULT", "payload": payload})
    return True


async def _send_event(websocket: WebSocket | None, event: ConversationEvent) -> None:
    global last_response
    message = event.as_dict()
    if message["state"] == "IDLE" and message.get("payload"):
        last_response = message["payload"]
        if engine.tts_client.is_playing():
            message = {"state": "SPEAKING", "payload": message["payload"]}
    await _send_or_broadcast(websocket, message)


async def _handle_graphify_command(text: str, websocket: WebSocket | None = None) -> bool:
    normalized = (text or "").strip().lower()
    if normalized not in {"graphify", "graphify ."} and not normalized.startswith("graphify "):
        return False
    target = text.strip().split(maxsplit=1)[1] if len(text.strip().split(maxsplit=1)) > 1 else "."
    engine.assistant_state.set_status(AssistantStatus.SEARCHING)
    await _send_or_broadcast(websocket, {"state": "GRAPHING", "payload": f"Graphify scanning {target}"})
    await _send_ui_event(websocket, "graphify scan")
    payload = await _build_graphify_payload(target)
    visual_result_history.append(payload)
    del visual_result_history[:-8]
    engine.assistant_state.set_status(AssistantStatus.DISPLAYING_RESULT)
    state = "GRAPH_READY" if payload.get("ok", True) else "ERROR"
    await _send_or_broadcast(websocket, {"state": state, "payload": payload})
    return True


async def _build_graphify_payload(target: str) -> dict:
    try:
        result = await asyncio.to_thread(
            build_local_graph,
            _resolve_graphify_target(target),
            PROJECT_ROOT / "graphify-out" / "local_graph.json",
        )
    except GraphifyParseError as error:
        return {
            "type": "visual_result",
            "mode": "graph",
            "presentation": "animated_scene",
            "animation_profile": "low_confidence",
            "ok": False,
            "title": "GraphifyParseError",
            "summary": str(error),
            "message": str(error),
            "nodes": [],
            "edges": [],
            "error": "GraphifyParseError",
            "sources": [target],
            "cost": {"operation": "graphify", "estimated_cost_usd": 0.0},
        }
    payload = dict(result.graph)
    payload["output_path"] = str(result.output_path)
    return payload


def _resolve_graphify_target(target: str):
    raw = (target or ".").strip().strip('"')
    path = (PROJECT_ROOT / raw).resolve() if not os.path.isabs(raw) else Path(raw).resolve()
    root = PROJECT_ROOT.resolve()
    try:
        path.relative_to(root)
    except ValueError as error:
        raise GraphifyParseError("Graphify target must stay inside the project directory.") from error
    return path


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
