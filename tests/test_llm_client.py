from types import SimpleNamespace

from src.llm import LLMClient
from src.llm_client import przygotuj_historie_do_api
from src.config import load_settings


def test_load_settings_zostawia_tani_model_gpt_4_1_mini():
    settings = load_settings()

    assert settings.llm_model == "gpt-4.1-mini"


def test_przygotuj_historie_do_api_ogranicza_kontekst_modelu_do_40_wiadomosci():
    historia = []

    for indeks in range(55):
        historia.append({
            "role": "user",
            "content": f"Wiadomosc {indeks}",
        })

    wynik = przygotuj_historie_do_api(historia)

    assert len(wynik) == 40, "do OpenAI powinno trafic najwyzej 40 ostatnich wiadomosci"
    assert wynik[0]["content"] == "Wiadomosc 15"
    assert wynik[-1]["content"] == "Wiadomosc 54"


def test_build_instructions_zawiera_styl_jarvisa_i_guardrail_przeciw_halucynacjom():
    instrukcje = LLMClient().build_instructions(long_term_memory=[])

    assert "J.A.R.V.I.S." in instrukcje
    assert "Iron Mana" in instrukcje
    assert "lekko ironiczny" in instrukcje
    assert "Nie wymyslasz faktow" in instrukcje
    assert "Katalog lokalnych komend JARVISA" in instrukcje
    assert "jarvis wylacz sie" in instrukcje


def test_generate_response_obsluguje_function_calling_i_odsyla_wynik_narzedzia():
    function_call = SimpleNamespace(
        type="function_call",
        call_id="call_123",
        name="add_task",
        arguments='{"title": "Sprawdzic testy function calling"}',
    )
    first_response = SimpleNamespace(output=[function_call], output_text="")
    final_response = SimpleNamespace(output=[], output_text="Dodalem zadanie do listy.")
    fake_client = _FakeOpenAIClient([first_response, final_response])
    executed_tools = []

    def execute_tool(name, arguments):
        executed_tools.append((name, arguments))
        return '{"ok": true, "result": {"id": 1}}'

    client = LLMClient()
    client._client = fake_client

    result = client.generate_response(
        history=[{"role": "user", "content": "Dodaj zadanie z testami."}],
        long_term_memory=[],
        tools=[{"type": "function", "name": "add_task"}],
        tool_executor=execute_tool,
    )

    assert result == "Dodalem zadanie do listy."
    assert executed_tools == [
        ("add_task", {"title": "Sprawdzic testy function calling"})
    ]
    assert len(fake_client.responses.requests) == 2
    assert fake_client.responses.requests[0]["tool_choice"] == "auto"
    assert {
        "type": "function_call_output",
        "call_id": "call_123",
        "output": '{"ok": true, "result": {"id": 1}}',
    } in fake_client.responses.requests[1]["input"]


def test_correct_transcript_uzywa_llm_i_zwraca_poprawiony_tekst():
    fake_client = _FakeOpenAIClient([
        SimpleNamespace(output=[], output_text="jarvis śpisz? sprawdz FastAPI")
    ])
    client = LLMClient()
    client._client = fake_client

    result = client.correct_transcript("dżarwis spisz sprawdz fast api")

    assert result == "jarvis śpisz? sprawdz FastAPI"
    assert fake_client.responses.requests[0]["model"] == client.settings.llm_model
    assert "Popraw tylko oczywiste bledy STT" in fake_client.responses.requests[0]["instructions"]
    assert fake_client.responses.requests[0]["input"] == [
        {"role": "user", "content": "dżarwis spisz sprawdz fast api"}
    ]


def test_correct_transcript_odrzuca_podejrzanie_dlugi_wynik():
    fake_client = _FakeOpenAIClient([
        SimpleNamespace(output=[], output_text="x" * 500)
    ])
    client = LLMClient()
    client._client = fake_client

    result = client.correct_transcript("open ai")

    assert result == "open ai"


class _FakeOpenAIClient:
    def __init__(self, responses):
        self.responses = _FakeResponses(responses)


class _FakeResponses:
    def __init__(self, responses):
        self._responses = list(responses)
        self.requests = []

    def create(self, **kwargs):
        self.requests.append(kwargs)
        return self._responses.pop(0)
