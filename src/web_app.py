from __future__ import annotations

import asyncio

from fastapi import FastAPI, WebSocket, WebSocketDisconnect
from fastapi.responses import FileResponse, RedirectResponse
from fastapi.staticfiles import StaticFiles

from src.config import PROJECT_ROOT, load_settings
from src.conversation_engine import ConversationEngine, ConversationEvent
from src.logger import configure_logging


settings = load_settings()
configure_logging(settings.log_level)
app = FastAPI(title="JARVIS Local UI")
engine = ConversationEngine(settings)
ui_dir = PROJECT_ROOT / "ui"

app.mount("/ui", StaticFiles(directory=ui_dir), name="ui")


@app.get("/")
def index() -> RedirectResponse:
    return RedirectResponse("/ui/index.html")


@app.websocket("/api/ws")
async def websocket_endpoint(websocket: WebSocket) -> None:
    await websocket.accept()
    await websocket.send_json({"state": "IDLE", "payload": "connected"})

    try:
        while True:
            message = await websocket.receive_json()
            message_type = str(message.get("type", "text"))

            if message_type == "stop":
                engine.stop_all()
                await websocket.send_json({"state": "IDLE", "payload": "stopped"})
                continue

            if message_type == "listen":
                await websocket.send_json({"state": "LISTENING", "payload": ""})
                text, utterance_end_time = await asyncio.to_thread(engine.listen_once)
                await websocket.send_json({"state": "LISTENING", "payload": text})
                if not text:
                    await websocket.send_json({"state": "IDLE", "payload": ""})
                    continue
            else:
                text = str(message.get("payload", "")).strip()
                utterance_end_time = None

            if not text:
                await websocket.send_json({"state": "IDLE", "payload": ""})
                continue

            for event in engine.stream_response(text, utterance_end_time):
                await websocket.send_json(event.as_dict())

    except WebSocketDisconnect:
        engine.stop_all()


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
