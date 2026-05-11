import os

from dotenv import load_dotenv
from openai import OpenAI, OpenAIError

from config import MODEL_LLM, SYSTEM_PROMPT


load_dotenv()

client = OpenAI(
    api_key=os.getenv("OPENAI_API_KEY")
)


def odpowiedz_jarvisa(historia: list[dict]) -> str:
    try:
        response = client.responses.create(
            model=MODEL_LLM,
            instructions=SYSTEM_PROMPT,
            input=historia
        )

        return response.output_text

    except OpenAIError as blad:
        return f"Wystąpił błąd po stronie OpenAI API: {blad}"

    except Exception as blad:
        return f"Wystąpił nieoczekiwany błąd programu: {blad}"