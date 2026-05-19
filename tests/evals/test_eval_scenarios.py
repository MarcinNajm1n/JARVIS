from src.command_catalog import search_command_catalog
from src.function_tools import JARVIS_FUNCTION_TOOLS
from src.llm import LLMClient


def test_eval_scenariusze_pokrywaja_kluczowe_obszary_jarvisa():
    tool_names = {tool["name"] for tool in JARVIS_FUNCTION_TOOLS}

    assert "mark_task_done" in tool_names
    assert "get_profile" in tool_names
    assert "get_project_status" in tool_names
    assert "search_memory" in tool_names
    assert "search_commands" in tool_names


def test_eval_aktywacja_i_wylaczanie_sa_odnajdywalne_w_katalogu_komend():
    results = search_command_catalog("jak moge cie wylaczyc")

    assert results[0]["command"] == "jarvis wylacz sie"


def test_eval_styl_odpowiedzi_jest_krotki_techniczny_i_bez_teatralnosci():
    instructions = LLMClient().build_instructions(long_term_memory=[])

    assert "konkretnie i praktycznie" in instructions
    assert "techniczny" in instructions
    assert "lekko ironiczny" in instructions
    assert "bez cytowania kwestii z filmu" in instructions
    assert "teatralnosci" in instructions


def test_eval_antyhalucynacyjny_guardrail_jest_w_promptcie():
    instructions = LLMClient().build_instructions(long_term_memory=[])

    assert "Nie wymyslasz faktow" in instructions
    assert "Jesli czegos nie wiesz, mowisz to wprost" in instructions
