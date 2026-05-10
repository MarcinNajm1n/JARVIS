from src.llm_client import odpowiedz_jarvisa


def test_odpowiedz_jarvisa_zwraca_tekst():
    wynik = odpowiedz_jarvisa("siema")

    assert isinstance(wynik, str)
    assert len(wynik) > 0