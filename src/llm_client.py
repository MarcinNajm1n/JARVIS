import os

from dotenv import load_dotenv
from openai import OpenAI, OpenAIError

from config import MODEL_LLM, SYSTEM_PROMPT, MAKSYMALNA_LICZBA_WIADOMOSCI
from src.debug_utils import debug_print


load_dotenv()


def pobierz_klucz_api() -> str:
    klucz_api = os.getenv("OPENAI_API_KEY")

    if not klucz_api:
        raise ValueError(
            "Brakuje klucza OPENAI_API_KEY. "
            "Sprawdź, czy masz plik .env i czy zawiera OPENAI_API_KEY=twoj_klucz."
        )

    return klucz_api


client = OpenAI(
    api_key=pobierz_klucz_api()
)


def zbuduj_instrukcje_z_pamiecia(pamiec_stala: list[str]) -> str:
    if len(pamiec_stala) == 0:
        return SYSTEM_PROMPT

    blok_pamieci = "\n".join([f"- {wpis}" for wpis in pamiec_stala])

    return f"""{SYSTEM_PROMPT}

Dodatkowa pamięć stała użytkownika:
{blok_pamieci}

Traktuj powyższe informacje jako trwałe fakty o użytkowniku,
o ile użytkownik nie poda później nowych informacji, które je zmieniają.
"""


def przygotuj_historie_do_api(historia: list[dict]) -> list[dict]:
    return historia[-MAKSYMALNA_LICZBA_WIADOMOSCI:]


def odpowiedz_jarvisa(historia: list[dict], pamiec_stala: list[str]) -> str:
    try:
        instrukcje = zbuduj_instrukcje_z_pamiecia(pamiec_stala)
        historia_do_api = przygotuj_historie_do_api(historia)

        debug_print(f"Używany model: {MODEL_LLM}")
        debug_print(f"Wiadomości w pełnej historii: {len(historia)}")
        debug_print(f"Wiadomości wysyłane do API: {len(historia_do_api)}")
        debug_print(f"Wpisy w pamięci stałej: {len(pamiec_stala)}")

        response = client.responses.create(
            model=MODEL_LLM,
            instructions=instrukcje,
            input=historia_do_api
        )

        return response.output_text

    except OpenAIError as blad:
        return f"Wystąpił błąd po stronie OpenAI API: {blad}"

    except Exception as blad:
        return f"Wystąpił nieoczekiwany błąd programu: {blad}"