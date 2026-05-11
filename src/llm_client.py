import os

from openai import OpenAI
from dotenv import load_dotenv

from config import MODEL_LLM


load_dotenv()

client = OpenAI(api_key=os.getenv("OPENAI_API_KEY"))


def odpowiedz_jarvisa(wiadomosc: str) -> str:
    response = client.responses.create(
        model=MODEL_LLM,
        input=wiadomosc
    )

    return response.output_text