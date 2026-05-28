import asyncio
from types import SimpleNamespace

import pytest

from src import web_app
from src.graphify_cli import GraphifyParseError
from src.retrieval.models import EvidenceChunk, QueryPlan, RetrievalResult, SearchMode
from src.weather_service import WeatherResult


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
        command_text=["dodaj zadanie sprawdzic function calling", "", ""],
    )
    websocket = _FakeWebSocket()

    async def scenario():
        monkeypatch.setattr(web_app, "engine", fake_engine)
        monkeypatch.setattr(web_app, "recording_lock", asyncio.Lock())
        await web_app._handle_wake_scan(websocket)

    asyncio.run(scenario())

    assert fake_engine.acknowledge_calls == 1
    assert fake_engine.listen_for_command_calls == 3
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
    assert any(message["state"] == "GOING_SLEEP" for message in websocket.messages)
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

    assert fake_engine.listen_for_command_calls == 4
    assert fake_engine.stream_calls == [("sprawdz status projektu", 123.0)]
    assert any(message["state"] == "GOING_SLEEP" for message in websocket.messages)


def test_web_wake_gate_po_odpowiedzi_przyjmuje_follow_up_bez_ponownej_aktywacji(monkeypatch):
    fake_engine = _FakeEngine(
        wake_text="jarvis spisz",
        command_text=["pierwsze pytanie", "drugie pytanie", "", ""],
    )
    websocket = _FakeWebSocket()

    async def scenario():
        monkeypatch.setattr(web_app, "engine", fake_engine)
        monkeypatch.setattr(web_app, "recording_lock", asyncio.Lock())
        await web_app._handle_wake_scan(websocket)

    asyncio.run(scenario())

    assert fake_engine.listen_for_command_calls == 4
    assert fake_engine.stream_calls == [
        ("pierwsze pytanie", 123.0),
        ("drugie pytanie", 123.0),
    ]
    assert websocket.messages[-1]["state"] == "SLEEPING"


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


def test_web_wake_gate_pogoda_wysyla_visual_result_bez_llm(monkeypatch):
    fake_engine = _FakeEngine(
        wake_text="jarvis spisz",
        command_text=["jaka jest pogoda w Berlinie", "", ""],
    )
    websocket = _FakeWebSocket()

    def fake_weather(location):
        return WeatherResult(
            ok=True,
            location="Berlin",
            lat=52.52,
            lon=13.405,
            temperature=18,
            description="pochmurno",
            wind=12,
            humidity=60,
            cloud_cover=75,
            observed_at="2026-05-20T12:00",
        )

    async def scenario():
        monkeypatch.setattr(web_app, "engine", fake_engine)
        monkeypatch.setattr(web_app, "recording_lock", asyncio.Lock())
        monkeypatch.setattr(web_app, "get_current_weather", fake_weather)
        await web_app._handle_wake_scan(websocket)

    asyncio.run(scenario())

    assert fake_engine.stream_calls == []
    assert any(message["state"] == "SEARCHING" for message in websocket.messages)
    visual_messages = [message for message in websocket.messages if message["state"] == "VISUAL_RESULT"]
    assert visual_messages
    assert visual_messages[0]["payload"]["mode"] == "map_weather"
    assert visual_messages[0]["payload"]["location"] == "Berlin"
    assert any(message["state"] == "UI_EVENT" for message in websocket.messages)


def test_web_weather_brak_danych_pokazuje_komunikat(monkeypatch):
    fake_engine = _FakeEngine(wake_text="")
    websocket = _FakeWebSocket()

    def fake_weather(location):
        return WeatherResult(False, location, error="Brak danych")

    async def scenario():
        monkeypatch.setattr(web_app, "engine", fake_engine)
        monkeypatch.setattr(web_app, "get_current_weather", fake_weather)
        handled = await web_app._handle_visual_query("pogoda w NieznaneMiasto", websocket)
        assert handled is True

    asyncio.run(scenario())

    visual_messages = [message for message in websocket.messages if message["state"] == "VISUAL_RESULT"]
    assert visual_messages[0]["payload"]["ok"] is False
    assert "Nie mam aktualnych danych pogodowych" in visual_messages[0]["payload"]["message"]
    assert fake_engine.stream_calls == []


def test_emergency_stop_zatrzymuje_silnik_i_broadcastuje_event(monkeypatch):
    fake_engine = _FakeEngine(wake_text="")
    websocket = _FakeWebSocket()

    async def scenario():
        monkeypatch.setattr(web_app, "engine", fake_engine)
        monkeypatch.setattr(web_app, "connected_websockets", {websocket})
        response = await web_app.emergency_stop()
        assert response["state"] == "EMERGENCY_STOP"

    asyncio.run(scenario())

    assert fake_engine.stop_all_calls == 1
    assert fake_engine.assistant_state.get_status() == "sleeping"
    assert any(message["state"] == "EMERGENCY_STOP" for message in websocket.messages)


def test_web_visual_planner_wysyla_entity_profile_dla_pytania_faktograficznego(monkeypatch):
    fake_engine = _FakeEngine(wake_text="")
    websocket = _FakeWebSocket()

    def fake_plan(question, answer):
        assert question == "kto jest najbogatszy na swiecie"
        assert answer == "Elon Musk jest przedsiebiorca."
        return {
            "type": "visual_result",
            "mode": "entity_profile",
            "title": "Elon Musk",
            "subject": "Elon Musk",
            "summary": "Profil testowy.",
            "facts": ["CEO kilku firm."],
            "sources": ["Wikipedia"],
            "cost": {"operation": "visual_planner", "estimated_cost_usd": 0.0},
        }

    async def scenario():
        monkeypatch.setattr(web_app, "engine", fake_engine)
        monkeypatch.setattr(web_app, "plan_visual_result", fake_plan)
        handled = await web_app._send_planned_visual_result(
            websocket,
            "kto jest najbogatszy na swiecie",
            "Elon Musk jest przedsiebiorca.",
        )
        assert handled is True

    asyncio.run(scenario())

    visual_messages = [message for message in websocket.messages if message["state"] == "VISUAL_RESULT"]
    assert visual_messages
    assert visual_messages[0]["payload"]["mode"] == "entity_profile"
    assert visual_messages[0]["payload"]["subject"] == "Elon Musk"


def test_web_graphify_command_wysyla_graph_ready(monkeypatch, tmp_path):
    fake_engine = _FakeEngine(wake_text="")
    websocket = _FakeWebSocket()
    (tmp_path / "A.md").write_text("[B](B.md)", encoding="utf-8")
    (tmp_path / "B.md").write_text("# B", encoding="utf-8")

    async def scenario():
        monkeypatch.setattr(web_app, "engine", fake_engine)
        monkeypatch.setattr(web_app, "PROJECT_ROOT", tmp_path)
        handled = await web_app._handle_graphify_command("graphify .", websocket)
        assert handled is True

    asyncio.run(scenario())

    graph_messages = [message for message in websocket.messages if message["state"] == "GRAPH_READY"]
    assert graph_messages
    assert graph_messages[0]["payload"]["mode"] == "graph"
    assert graph_messages[0]["payload"]["nodes"]
    assert graph_messages[0]["payload"]["edges"]


def test_web_graphify_target_musi_zostac_w_katalogu_projektu(monkeypatch, tmp_path):
    project_root = tmp_path / "project"
    outside = tmp_path / "outside"
    project_root.mkdir()
    outside.mkdir()
    monkeypatch.setattr(web_app, "PROJECT_ROOT", project_root)

    with pytest.raises(GraphifyParseError):
        web_app._resolve_graphify_target(str(outside))


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


def test_web_realtime_generuje_hud_i_tts_czyta_tylko_spoken_answer(monkeypatch):
    fake_engine = _FakeEngine(wake_text="")
    websocket = _FakeWebSocket()
    result = RetrievalResult(
        question="co najnowszego wiadomo o OpenAI?",
        checked_at="2026-05-21T12:00:00+02:00",
        plan=QueryPlan(
            original_question="co najnowszego wiadomo o OpenAI?",
            needs_realtime=True,
            mode=SearchMode.NEWS,
            search_queries=["OpenAI news"],
            preferred_sources=[],
            reason="test",
        ),
        evidence=[
            EvidenceChunk(
                source_url="https://openai.com/news",
                source_title="OpenAI news",
                text="OpenAI opublikowalo aktualne informacje.",
                relevance_score=0.9,
                trust_score=0.86,
            )
        ],
        operations=[{"name": "SEARCHING_TAVILY", "status": "done", "duration_ms": 20}],
    )

    async def scenario():
        monkeypatch.setattr(web_app, "engine", fake_engine)
        await web_app._generate_realtime_response(
            websocket,
            "co najnowszego wiadomo o OpenAI?",
            "prompt",
            result,
        )

    asyncio.run(scenario())

    visual_messages = [message for message in websocket.messages if message["state"] == "VISUAL_RESULT"]
    assert visual_messages
    assert visual_messages[0]["payload"]["mode"] == "jarvis_tactical_hud"
    assert fake_engine.tts_client.speak_calls[-1][0] == "Krotko do TTS."
    assert "https://" not in fake_engine.tts_client.speak_calls[-1][0]


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


def test_web_wake_gate_naturalna_dezaktywacja_wysyla_shutdown(monkeypatch):
    fake_engine = _FakeEngine(wake_text="jarvis dezaktywacja")
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
        monkeypatch.setattr(web_app, "last_response", "Komenda przetworzona.")
        monkeypatch.setattr(web_app.asyncio, "sleep", fake_sleep)
        await web_app._settle_after_response(websocket, return_to_sleeping=True)

    asyncio.run(scenario())

    remaining_sleep_delay = (
        web_app.settings.post_speech_sleep_delay_seconds
        - web_app.settings.response_text_clear_delay_seconds
    )
    assert sleep_calls == [
        0.15,
        web_app.settings.response_text_clear_delay_seconds,
        remaining_sleep_delay,
    ]
    assert any(message["state"] == "CLEAR_TRANSCRIPT" for message in websocket.messages)
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
        self.wake_detector = _FakeWakeDetector(self.stt_client)
        self.episodic_memory = _FakeEpisodicMemory()
        self.cost_tracker = _FakeCostTracker()
        self.last_route_decision = None

    def acknowledge_wake_detected(self):
        self.acknowledge_calls += 1

    def correct_transcript(self, text, allow_llm=True):
        return text

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

    def generate_realtime_response(self, original_user_text, prompt_text):
        return (
            '{"answer":"Pelna odpowiedz z linkiem https://openai.com/news",'
            '"spoken_answer":"Krotko do TTS.",'
            '"confidence":"high",'
            '"display_type":"jarvis_tactical_hud",'
            '"checked_at":"2026-05-21T12:00:00+02:00",'
            '"sources":[{"title":"OpenAI news","url":"https://openai.com/news","summary":"news"}],'
            '"operations":[],'
            '"visual_assets":[]}'
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


class _FakeWakeDetector:
    def __init__(self, stt_client):
        self.stt_client = stt_client

    def detect_from_text(self, text):
        return SimpleNamespace(
            activated=self.stt_client.contains_wake_phrase(text),
            method="fake",
            confidence=0.9,
        )

    def status(self):
        return "fake-wake-ready"


class _FakeEpisodicMemory:
    def recent_context(self, limit=5):
        return "Brak epizodycznego kontekstu rozmowy."

    def snapshot(self):
        return {"events_count": 0, "recent_context": self.recent_context()}


class _FakeCostTracker:
    def snapshot(self):
        return {
            "model": "gpt-4.1-mini",
            "input_tokens": 0,
            "output_tokens": 0,
            "estimated_cost_usd": 0.0,
            "records_count": 0,
        }


class _FakeSttClient:
    def __init__(self, wake_text):
        self.wake_text = wake_text

    def listen_and_transcribe(self, max_seconds=None):
        return self.wake_text

    def contains_wake_phrase(self, text):
        lowered = text.lower()
        return 'jarvis' in lowered and ('spisz' in lowered or 'pisz' in lowered)

