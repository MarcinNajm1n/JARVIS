from openai import OpenAI
from dotenv import load_dotenv


load_dotenv()

client = OpenAI()


def odpowiedz_jarvisa(wiadomosc: str) -> str:
    """
    Tymczasowa funkcja udająca odpowiedź modelu AI.
    Później podmienimy jej wnętrze na prawdziwe API.
    """

    if wiadomosc.lower() in ["siema", "cześć", "czesc", "hej"]:
        return "Witaj. Jestem gotowy do pracy."

    if "jak się masz" in wiadomosc.lower() or "jak sie masz" in wiadomosc.lower():
        return "Działam poprawnie. Wszystkie moduły są w trybie testowym."

    return f"Tryb testowy: odebrałem wiadomość: {wiadomosc}"


    return response.output_text