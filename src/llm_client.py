import os

from dotenv import load_dotenv
from openai import OpenAI

from config import MODEL_LLM, SYSTEM_PROMPT


load_dotenv()

client = OpenAI(
    api_key=os.getenv("OPENAI_API_KEY")
)


def odpowiedz_jarvisa(wiadomosc: str) -> str:
    response = client.responses.create(
        model=MODEL_LLM,
        instructions=SYSTEM_PROMPT,
        input=wiadomosc
    )

    return response.output_text