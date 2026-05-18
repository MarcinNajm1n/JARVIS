from __future__ import annotations

from openai import OpenAI

from src.config import load_settings, require_openai_api_key
from src.llm import LLMClient, Message


def pobierz_klucz_api() -> str:
    return require_openai_api_key(load_settings())


def utworz_klienta_openai() -> OpenAI:
    return OpenAI(api_key=pobierz_klucz_api())


def zbuduj_instrukcje_z_pamiecia(pamiec_stala: list[str]) -> str:
    return LLMClient().build_instructions(pamiec_stala)


def przygotuj_historie_do_api(historia: list[Message]) -> list[Message]:
    return LLMClient().trim_history(historia)


def odpowiedz_jarvisa(historia: list[Message], pamiec_stala: list[str]) -> str:
    return LLMClient().generate_response(historia, pamiec_stala)
