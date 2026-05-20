from src.intent_router import IntentType, RouteType, classify_intent


def test_router_rozpoznaje_lokalne_intencje_bez_llm():
    assert classify_intent("jarvis aktywacja").intent == IntentType.ACTIVATION
    assert classify_intent("jarvis dezaktywacja").intent == IntentType.SHUTDOWN
    assert classify_intent("powtorz").intent == IntentType.REPEAT
    assert classify_intent("mow ciszej").intent == IntentType.VOLUME_DOWN
    assert classify_intent("pokaz status").intent == IntentType.STATUS


def test_router_wybiera_pamiec_rag_tool_i_llm():
    assert classify_intent("zapamietaj ze lubie krotkie odpowiedzi").route == RouteType.MEMORY
    assert classify_intent("przeczytaj dokument decyzje pdf").route == RouteType.RAG
    assert classify_intent("dodaj zadanie sprawdzic STT").route == RouteType.TOOL
    assert classify_intent("co myslisz o architekturze").route == RouteType.LLM
