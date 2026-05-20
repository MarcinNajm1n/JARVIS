from src.assistant_state import AssistantStatus
from src.intent_router import IntentType, RouteType, classify_intent
from src.local_wake_detector import LocalWakeDetector
from src.stt import SpeechToTextClient


def test_eval_ciagla_rozmowa_ma_stany_sesji():
    assert AssistantStatus.ACTIVE_CONVERSATION.value == "active_conversation"
    assert AssistantStatus.WAITING_FOLLOWUP.value == "waiting_followup"
    assert AssistantStatus.GOING_SLEEP.value == "going_sleep"


def test_eval_router_kieruje_tanie_intencje_poza_llm():
    local = classify_intent("pokaz status")
    memory = classify_intent("zapamietaj ze lubie techniczne odpowiedzi")
    rag = classify_intent("przeczytaj dokument decyzje")
    tool = classify_intent("dodaj zadanie sprawdzic UI")

    assert local.route == RouteType.LOCAL
    assert memory.route == RouteType.MEMORY
    assert rag.route == RouteType.RAG
    assert tool.route == RouteType.TOOL


def test_eval_lokalny_wake_detector_nie_potrzebuje_llm_do_aktywacji():
    detector = LocalWakeDetector(SpeechToTextClient())

    result = detector.detect_from_text("jarvis online")

    assert result.activated is True
    assert result.method == "local_intent"
    assert classify_intent("jarvis online").intent == IntentType.ACTIVATION
