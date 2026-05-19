import json
from datetime import datetime
from pathlib import Path
from typing import Any


SCIEZKA_PAMIECI_STALEJ = Path("data/long_term_memory.json")
MEMORY_TYPES = {"profile", "preferences", "projects", "facts", "decisions"}


def wczytaj_pamiec_stala(sciezka: Path = SCIEZKA_PAMIECI_STALEJ) -> list[Any]:
    if not sciezka.exists():
        return []

    try:
        with open(sciezka, "r", encoding="utf-8") as plik:
            return json.load(plik)
    except (json.JSONDecodeError, OSError):
        return []


def zapisz_pamiec_stala(
    pamiec_stala: list[Any],
    sciezka: Path = SCIEZKA_PAMIECI_STALEJ,
) -> None:
    sciezka.parent.mkdir(parents=True, exist_ok=True)

    with open(sciezka, "w", encoding="utf-8") as plik:
        json.dump(pamiec_stala, plik, ensure_ascii=False, indent=4)


def dodaj_do_pamieci_stalej(pamiec_stala: list[Any], wpis: str) -> list[Any]:
    wpis = wpis.strip()

    if wpis and wpis not in pamiec_stala:
        pamiec_stala.append(wpis)

    return pamiec_stala


def dodaj_wpis_pamieci(
    pamiec_stala: list[Any],
    content: str,
    memory_type: str = "facts",
) -> dict[str, Any] | None:
    content = content.strip()
    if not content:
        return None

    memory_type = _normalize_memory_type(memory_type)
    entries = normalizuj_wpisy_pamieci(pamiec_stala)
    if any(entry["content"] == content for entry in entries):
        return None

    entry = {
        "id": _next_memory_id(entries),
        "type": memory_type,
        "content": content,
        "created_at": datetime.now().isoformat(timespec="seconds"),
        "updated_at": None,
    }
    pamiec_stala.append(entry)
    return entry


def edytuj_wpis_pamieci(
    pamiec_stala: list[Any],
    entry_id: int,
    content: str | None = None,
    memory_type: str | None = None,
) -> dict[str, Any] | None:
    entries = normalizuj_wpisy_pamieci(pamiec_stala)
    for index, entry in enumerate(entries):
        if int(entry["id"]) != entry_id:
            continue
        if content is not None and content.strip():
            entry["content"] = content.strip()
        if memory_type is not None and memory_type.strip():
            entry["type"] = _normalize_memory_type(memory_type)
        entry["updated_at"] = datetime.now().isoformat(timespec="seconds")
        pamiec_stala[:] = entries
        return entries[index]
    return None


def usun_wpis_pamieci(pamiec_stala: list[Any], entry_id: int) -> bool:
    entries = normalizuj_wpisy_pamieci(pamiec_stala)
    filtered = [entry for entry in entries if int(entry["id"]) != entry_id]
    if len(filtered) == len(entries):
        return False
    pamiec_stala[:] = filtered
    return True


def szukaj_pamieci(pamiec_stala: list[Any], query: str) -> list[dict[str, Any]]:
    normalized_query = _normalize_text(query)
    query_terms = set(normalized_query.split())
    results: list[tuple[int, dict[str, Any]]] = []
    for entry in normalizuj_wpisy_pamieci(pamiec_stala):
        haystack = _normalize_text(f"{entry['type']} {entry['content']}")
        score = sum(1 for term in query_terms if term in haystack)
        if normalized_query and normalized_query in haystack:
            score += 5
        if score > 0:
            results.append((score, entry))
    results.sort(key=lambda item: item[0], reverse=True)
    return [entry for _score, entry in results[:8]]


def normalizuj_wpisy_pamieci(pamiec_stala: list[Any]) -> list[dict[str, Any]]:
    entries = []
    next_id = 1
    for item in pamiec_stala:
        if isinstance(item, dict):
            entry = {
                "id": int(item.get("id", next_id)),
                "type": _normalize_memory_type(str(item.get("type", "facts"))),
                "content": str(item.get("content", "")).strip(),
                "created_at": item.get("created_at"),
                "updated_at": item.get("updated_at"),
            }
        else:
            entry = {
                "id": next_id,
                "type": "facts",
                "content": str(item).strip(),
                "created_at": None,
                "updated_at": None,
            }
        if entry["content"]:
            entries.append(entry)
            next_id = max(next_id + 1, int(entry["id"]) + 1)
    return entries


def formatuj_pamiec_stala(pamiec_stala: list[Any]) -> str:
    if len(pamiec_stala) == 0:
        return "Pamiec stala jest pusta."

    wynik = "Pamiec stala:\n"

    for entry in normalizuj_wpisy_pamieci(pamiec_stala):
        wynik += f"{entry['id']}. [{entry['type']}] {entry['content']}\n"

    return wynik.strip()


def formatuj_pamiec_do_promptu(pamiec_stala: list[Any]) -> str:
    entries = normalizuj_wpisy_pamieci(pamiec_stala)
    if not entries:
        return ""
    return "\n".join(
        f"- ({entry['type']}, id={entry['id']}) {entry['content']}"
        for entry in entries
    )


def formatuj_memory_review(pamiec_stala: list[Any]) -> str:
    entries = normalizuj_wpisy_pamieci(pamiec_stala)
    if not entries:
        return "Pamiec JARVISA jest pusta."

    lines = ["Przeglad pamieci JARVISA:"]
    for memory_type in sorted(MEMORY_TYPES):
        grouped = [entry for entry in entries if entry["type"] == memory_type]
        if not grouped:
            continue
        lines.append(f"\n[{memory_type}]")
        for entry in grouped:
            lines.append(f"{entry['id']}. {entry['content']}")
    return "\n".join(lines).strip()


def wyczysc_pamiec_stala(sciezka: Path = SCIEZKA_PAMIECI_STALEJ) -> None:
    zapisz_pamiec_stala([], sciezka)


def _normalize_memory_type(memory_type: str) -> str:
    normalized = memory_type.strip().lower()
    return normalized if normalized in MEMORY_TYPES else "facts"


def _next_memory_id(entries: list[dict[str, Any]]) -> int:
    return max((int(entry.get("id", 0)) for entry in entries), default=0) + 1


def _normalize_text(text: str) -> str:
    translation = str.maketrans("ąćęłńóśźż", "acelnoszz")
    return " ".join(text.lower().translate(translation).split())
