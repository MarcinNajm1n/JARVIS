from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True)
class JarvisCommand:
    command: str
    description: str
    category: str
    examples: tuple[str, ...] = ()


COMMAND_CATALOG: tuple[JarvisCommand, ...] = (
    JarvisCommand("/zapamietaj tresc", "zapisz informacje do pamieci stalej", "pamiec"),
    JarvisCommand("/pamiec", "pokaz pamiec stala", "pamiec"),
    JarvisCommand("/memory review", "pokaz pamiec JARVISA pogrupowana wedlug typow", "pamiec"),
    JarvisCommand("/memory edit id tresc", "edytuj wpis pamieci", "pamiec"),
    JarvisCommand("/memory remove id", "usun wpis pamieci", "pamiec"),
    JarvisCommand("/wyczysc_pamiec", "wyczysc pamiec stala po potwierdzeniu", "pamiec"),
    JarvisCommand("/wyczysc_historie", "wyczysc historie rozmowy po potwierdzeniu", "historia"),
    JarvisCommand("/reset", "zresetuj kontekst rozmowy bez naruszania pamieci stalej", "historia"),
    JarvisCommand("/status", "pokaz stan historii, pamieci, glosu, trybu i projektu", "system"),
    JarvisCommand("/env status", "pokaz bezpieczna diagnostyke klucza API bez ujawniania sekretu", "system"),
    JarvisCommand("/model", "pokaz aktualny model LLM", "system"),
    JarvisCommand("/voice on/off/status", "wlacz, wylacz lub sprawdz TTS", "glos"),
    JarvisCommand("/voice openai", "przelacz STT/TTS na standardowy provider OpenAI", "glos"),
    JarvisCommand("/voice elevenlabs", "przelacz STT/TTS na provider ElevenLabs, jesli jest wlaczony w .env", "glos"),
    JarvisCommand("/stop", "przerwij aktualne odtwarzanie TTS", "glos"),
    JarvisCommand("stop", "glosowo przerwij aktualne odtwarzanie TTS", "glos"),
    JarvisCommand("jarvis stop", "glosowo przerwij aktualne odtwarzanie TTS", "glos"),
    JarvisCommand("przestan", "glosowo przerwij aktualne odtwarzanie TTS", "glos"),
    JarvisCommand("koniec", "glosowo przerwij aktualne odtwarzanie TTS", "glos"),
    JarvisCommand("skoncz", "glosowo przerwij aktualne odtwarzanie TTS", "glos"),
    JarvisCommand(
        "jarvis wylacz sie",
        "zapisz dane i zakoncz dzialanie programu",
        "system",
        ("jarvis wyłącz się", "jarvis wylacz sie"),
    ),
    JarvisCommand("/debug on/off/status", "wlacz, wylacz lub sprawdz debug", "system"),
    JarvisCommand("/rag status", "pokaz stan lokalnej bazy wiedzy", "rag"),
    JarvisCommand("/rag index", "przebuduj indeks dokumentow", "rag"),
    JarvisCommand("/mode nazwa", "ustaw tryb odpowiedzi: jarvis, mentor, szybki, techniczny", "tryb"),
    JarvisCommand("/profile", "pokaz profil uzytkownika", "profil"),
    JarvisCommand("/profile set k v", "ustaw pole profilu", "profil"),
    JarvisCommand("/task add tresc", "dodaj zadanie", "zadania"),
    JarvisCommand("/task list", "pokaz zadania", "zadania"),
    JarvisCommand("/task done id", "oznacz zadanie jako wykonane", "zadania"),
    JarvisCommand("/task remove id", "usun zadanie", "zadania"),
    JarvisCommand("/project nazwa", "ustaw aktywny projekt", "projekt"),
    JarvisCommand("/project status", "pokaz aktywny projekt", "projekt"),
    JarvisCommand("/project log tresc", "dodaj notatke do projektu", "projekt"),
    JarvisCommand("/project list", "pokaz projekty", "projekt"),
    JarvisCommand("/project stop", "wylacz aktywny projekt", "projekt"),
    JarvisCommand("/briefing", "pokaz dzienny briefing operacyjny", "briefing"),
    JarvisCommand("/feedback dobra", "zapisz pozytywna ocene odpowiedzi", "feedback"),
    JarvisCommand("/feedback zla", "zapisz negatywna ocene odpowiedzi", "feedback"),
    JarvisCommand("/input text", "przelacz wejscie na klawiature", "wejscie"),
    JarvisCommand("/input voice", "przelacz wejscie na mikrofon", "wejscie"),
    JarvisCommand("/input wake", "nasluchuj frazy 'jarvis śpisz?'", "wejscie"),
    JarvisCommand("/pomoc", "pokaz dostepne komendy", "pomoc"),
    JarvisCommand("exit", "zakoncz program w trybie terminalowym", "system"),
)


def format_command_help() -> str:
    lines = ["Dostepne komendy:"]
    for item in COMMAND_CATALOG:
        lines.append(f"{item.command:<24} - {item.description}")
    return "\n".join(lines)


def format_command_catalog_for_prompt() -> str:
    lines = [
        "Katalog lokalnych komend JARVISA:",
        "Gdy uzytkownik pyta, jak wykonac lokalna akcje, odpowiadaj na podstawie tej listy.",
        "Przy pytaniu o wylaczenie programu powiedz: mozesz mnie wylaczyc za pomoca zwyklego 'jarvis wylacz sie'.",
    ]
    for item in COMMAND_CATALOG:
        examples = f" Przyklady: {', '.join(item.examples)}." if item.examples else ""
        lines.append(
            f"- [{item.category}] {item.command}: {item.description}.{examples}"
        )
    return "\n".join(lines)


def search_command_catalog(query: str) -> list[dict[str, str]]:
    normalized_query = _normalize(query)
    query_terms = set(normalized_query.split())
    results: list[tuple[int, JarvisCommand]] = []

    for item in COMMAND_CATALOG:
        haystack = _normalize(
            " ".join((item.command, item.description, item.category, " ".join(item.examples)))
        )
        score = sum(1 for term in query_terms if term in haystack)
        if normalized_query and normalized_query in haystack:
            score += 5
        if _is_shutdown_query(normalized_query) and item.command == "jarvis wylacz sie":
            score += 10
        if score > 0:
            results.append((score, item))

    results.sort(key=lambda result: result[0], reverse=True)
    return [
        {
            "command": item.command,
            "description": item.description,
            "category": item.category,
            "examples": ", ".join(item.examples),
        }
        for _score, item in results[:8]
    ]


def _is_shutdown_query(query: str) -> bool:
    return any(term in query for term in ("wylaczyc", "wylacz", "zamknac", "zamknij", "zakonczyc"))


def _normalize(text: str) -> str:
    translation = str.maketrans("ąćęłńóśźż", "acelnoszz")
    return " ".join(text.lower().translate(translation).split())
