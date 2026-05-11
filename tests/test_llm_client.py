from src.llm_client import przygotuj_historie_do_api


def test_przygotuj_historie_do_api_ogranicza_liczbe_wiadomosci():
    historia = []

    for indeks in range(20):
        historia.append({
            "role": "user",
            "content": f"Wiadomość {indeks}"
        })

    wynik = przygotuj_historie_do_api(historia)

    assert len(wynik) == 10
    assert wynik[0]["content"] == "Wiadomość 10"
    assert wynik[-1]["content"] == "Wiadomość 19"