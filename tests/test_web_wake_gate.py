import asyncio
from types import SimpleNamespace

from src import web_app


def test_web_wake_gate_nie_wysyla_do_llm_bez_frazy_aktywacji(monkeypatch):
    fake_engine = _FakeEngine(wake_text="dodaj zadanie sprawdzic logi")
    websocket = _FakeWebSocket()

    async def scenario():
        monkeypatch.setattr(web_app, "engine", fake_engine)
        monkeypatch.setattr(web_app, "recording_lock", asyncio.Lock())
        await web_app._handle_wake_scan(websocket)

    asyncio.run(scenario())

    assert fake_engine.listen_for_command_calls == 0
    assert fake_engine.stream_calls == []
    assert fake_engine.historia == []
    assert any(
        message["payload"] == "Czekam na fraze: jarvis śpisz?"
        for message in websocket.messages
    )


def test_web_wake_gate_po_aktywacji_wysyla_do_llm_tylko_komende(monkeypatch):
    fake_engine = _FakeEngine(
        wake_text="jarvis śpisz?",
        command_text="dodaj zadanie sprawdzic function calling",
    )
    websocket = _FakeWebSocket()

    async def scenario():
        monkeypatch.setattr(web_app, "engine", fake_engine)
        monkeypatch.setattr(web_app, "recording_lock", asyncio.Lock())
        await web_app._handle_wake_scan(websocket)

    asyncio.run(scenario())

    assert fake_engine.acknowledge_calls == 1
    assert fake_engine.listen_for_command_calls == 1
    assert fake_engine.stream_calls == [
        ("dodaj zadanie sprawdzic function calling", 123.0)
    ]
    assert all("jarvis śpisz" not in call[0].lower() for call in fake_engine.stream_calls)
    assert any(
        message["payload"] == "Transkrypcja robocza: jarvis śpisz?"
        for message in websocket.messages
    )
    assert any(message["state"] == "WAKE_DETECTED" for message in websocket.messages)
    assert any(message["state"] == "LISTENING_COMMAND" for message in websocket.messages)


def test_web_wake_gate_timeout_po_aktywacji_nie_wysyla_do_llm(monkeypatch):
    fake_engine = _FakeEngine(wake_text="jarvis śpisz?", command_text="")
    websocket = _FakeWebSocket()

    async def scenario():
        monkeypatch.setattr(web_app, "engine", fake_engine)
        monkeypatch.setattr(web_app, "recording_lock", asyncio.Lock())
        await web_app._handle_wake_scan(websocket)

    asyncio.run(scenario())

    assert fake_engine.listen_for_command_calls == 2
    assert fake_engine.stream_calls == []
    assert any(message["state"] == "AWAKE_CONFIRM" for message in websocket.messages)
    assert any(message["payload"] == "Mogę iść spać, szefie?" for message in websocket.messages)
    assert any(message["payload"] == "Wracam do snu." for message in websocket.messages)


def test_web_wake_gate_po_pytaniu_o_sen_przyjmuje_spozniona_komende(monkeypatch):
    fake_engine = _FakeEngine(
        wake_text="jarvis śpisz?",
        command_text=["", "sprawdz status projektu"],
    )
    websocket = _FakeWebSocket()

    async def scenario():
        monkeypatch.setattr(web_app, "engine", fake_engine)
        monkeypatch.setattr(web_app, "recording_lock", asyncio.Lock())
        await web_app._handle_wake_scan(websocket)

    asyncio.run(scenario())

    assert fake_engine.listen_for_command_calls == 2
    assert fake_engine.stream_calls == [("sprawdz status projektu", 123.0)]
    assert any(message["state"] == "AWAKE_CONFIRM" for message in websocket.messages)


def test_web_wake_gate_lokalna_komenda_stop_przerywa_tts_bez_llm(monkeypatch):
    fake_engine = _FakeEngine(wake_text="jarvis śpisz?", command_text="stop")
    websocket = _FakeWebSocket()

    async def scenario():
        monkeypatch.setattr(web_app, "engine", fake_engine)
        monkeypatch.setattr(web_app, "recording_lock", asyncio.Lock())
        await web_app._handle_wake_scan(websocket)

    asyncio.run(scenario())

    assert fake_engine.stop_audio_calls == 1
    assert fake_engine.stream_calls == []
    assert any(
        message["payload"] == "Przerywam odtwarzanie."
        for message in websocket.messages
    )


def test_web_wake_gate_jarvis_stop_przerywa_tts_bez_frazy_aktywacji(monkeypatch):
    fake_engine = _FakeEngine(wake_text="jarvis stop")
    websocket = _FakeWebSocket()

    async def scenario():
        monkeypatch.setattr(web_app, "engine", fake_engine)
        monkeypatch.setattr(web_app, "recording_lock", asyncio.Lock())
        await web_app._handle_wake_scan(websocket)

    asyncio.run(scenario())

    assert fake_engine.stop_audio_calls == 1
    assert fake_engine.listen_for_command_calls == 0
    assert fake_engine.stream_calls == []


def test_web_wake_gate_jarvis_wylacz_sie_wysyla_shutdown(monkeypatch):
    fake_engine = _FakeEngine(wake_text="jarvis wylacz sie")
    websocket = _FakeWebSocket()
    shutdown_calls = []

    async def scenario():
        monkeypatch.setattr(web_app, "engine", fake_engine)
        monkeypatch.setattr(web_app, "recording_lock", asyncio.Lock())
        monkeypatch.setattr(web_app, "zapisz_historie", lambda *_args, **_kwargs: None)
        monkeypatch.setattr(web_app, "zapisz_pamiec_stala", lambda *_args, **_kwargs: None)
        monkeypatch.setattr(
            web_app,
            "_shutdown_process_soon",
            lambda: shutdown_calls.append(True),
        )
        await web_app._handle_wake_scan(websocket)

    asyncio.run(scenario())

    assert shutdown_calls == [True]
    assert fake_engine.stop_all_calls == 1
    assert fake_engine.listen_for_command_calls == 0
    assert fake_engine.stream_calls == []
    assert any(message["state"] == "SHUTDOWN" for message in websocket.messages)


def test_clear_working_transcripts_czysci_wake_i_odpowiedz(monkeypatch):
    fake_engine = _FakeEngine(wake_text="")
    websocket = _FakeWebSocket()

    async def scenario():
        monkeypatch.setattr(web_app, "engine", fake_engine)
        monkeypatch.setattr(web_app, "last_wake_transcript", "roboczy tekst")
        monkeypatch.setattr(web_app, "last_response", "ostatnia odpowiedz")
        await web_app._clear_working_transcripts(websocket)

    asyncio.run(scenario())

    assert web_app.last_wake_transcript == ""
    assert web_app.last_response == ""
    assert any(
        message["payload"] == "Wyczyszczono transkrypcje robocze."
        for message in websocket.messages
    )


def test_settle_after_response_czeka_na_koniec_tts_i_pauze_przed_snem(monkeypatch):
    fake_engine = _FakeEngine(wake_text="")
    fake_engine.tts_client = _FakeTtsClient([True, False])
    websocket = _FakeWebSocket()
    sleep_calls = []

    async def fake_sleep(seconds):
        sleep_calls.append(seconds)

    async def scenario():
        monkeypatch.setattr(web_app, "engine", fake_engine)
        monkeypatch.setattr(web_app.asyncio, "sleep", fake_sleep)
        await web_app._settle_after_response(websocket, return_to_sleeping=True)

    asyncio.run(scenario())

    assert sleep_calls == [0.15, web_app.settings.post_speech_sleep_delay_seconds]
    assert websocket.messages[-1]["state"] == "SLEEPING"
    assert fake_engine.assistant_state.get_status() == "sleeping"


class _FakeWebSocket:
    def __init__(self):
        self.messages = []

    async def send_json(self, message):
        self.messages.append(message)


class _FakeEngine:
    def __init__(self, wake_text, command_text=""):
        self.stt_client = _FakeSttClient(wake_text)
        if isinstance(command_text, list):
            self.command_texts = command_text
        else:
            self.command_texts = [command_text]
        self.acknowledge_calls = 0
        self.listen_for_command_calls = 0
        self.stop_audio_calls = 0
        self.stop_all_calls = 0
        self.stream_calls = []
        self.historia = []
        self.history_enabled = True
        self.task_store = _FakeTaskStore()
        self.project_store = _FakeProjectStore()
        self.assistant_state = _FakeAssistantState()
        self.tts_client = _FakeTtsClient()
        self.pamiec_stala = []
        self.rag_memory = _FakeRagMemory()

    def acknowledge_wake_detected(self):
        self.acknowledge_calls += 1

    def listen_for_command(self, max_seconds=None):
        self.listen_for_command_calls += 1
        if self.command_texts:
            return self.command_texts.pop(0), 123.0
        return "", 123.0

    def stop_audio(self):
        self.stop_audio_calls += 1

    def stop_all(self):
        self.stop_all_calls += 1

    def stream_response(self, text, utterance_end_time):
        self.stream_calls.append((text, utterance_end_time))
        yield SimpleNamespace(
            as_dict=lambda: {
                "state": "IDLE",
                "payload": "Komenda przetworzona.",
            }
        )

    def get_memory_candidate(self, text):
        return None

    def save_memory_candidate(self, candidate, memory_type="facts"):
        return True


class _FakeTaskStore:
    def list(self, include_done=True):
        return []


class _FakeProjectStore:
    def summarize(self, active_project):
        return "Brak aktywnego projektu."


class _FakeAssistantState:
    _state = {"last_status": "sleeping"}

    def get_active_project(self):
        return None

    def get_status(self):
        return self._state["last_status"]

    def set_status(self, status):
        self._state["last_status"] = getattr(status, "value", str(status))


class _FakeTtsClient:
    def __init__(self, playing_states=None):
        self.playing_states = list(playing_states or [])
        self.speak_calls = []

    def speak(self, text, blocking=None):
        self.speak_calls.append((text, blocking))
        return True

    def is_playing(self):
        if not self.playing_states:
            return False
        return self.playing_states.pop(0)


class _FakeRagMemory:
    def status(self):
        return "RAG: disabled; documents: 0; index: not built; directory: data/documents"


class _FakeSttClient:
    def __init__(self, wake_text):
        self.wake_text = wake_text

    def listen_and_transcribe(self, max_seconds=None):
        return self.wake_text

    def contains_wake_phrase(self, text):
        return "jarvis śpisz" in text.lower()
