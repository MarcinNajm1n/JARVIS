from __future__ import annotations


RESPONSE_MODES = {
    "jarvis": (
        "Tryb odpowiedzi: JARVIS. Odpowiadaj elegancko, rzeczowo, spokojnie i "
        "z lekkim stylem prywatnego asystenta technicznego. Bez teatralnosci."
    ),
    "mentor": (
        "Tryb odpowiedzi: mentor. Tlumacz krok po kroku, ale zwiezle. "
        "Zakladaj, ze uzytkownik zna podstawy AI i uczy sie praktyki."
    ),
    "szybki": (
        "Tryb odpowiedzi: szybki. Odpowiadaj bardzo krotko, decyzyjnie, "
        "najpierw konkret, potem ewentualnie jeden nastepny krok."
    ),
    "techniczny": (
        "Tryb odpowiedzi: techniczny. Uzywaj precyzyjnego jezyka inzynierskiego, "
        "wymieniaj zalozenia, ryzyka i konkretne komendy lub pliki."
    ),
}


def list_modes() -> list[str]:
    return sorted(RESPONSE_MODES)


def get_mode_instruction(mode: str) -> str:
    return RESPONSE_MODES.get(mode, RESPONSE_MODES["jarvis"])
