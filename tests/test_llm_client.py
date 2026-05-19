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
