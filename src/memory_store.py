import json
from datetime import datetime
from pathlib import Path
from typing import Any


SCIEZKA_HISTORII = Path("data/conversation_history.json")
SCIEZKA_PODSUMOWANIA_HISTORII = Path("data/conversation_summary.json")
MAKSYMALNA_LICZBA_WIADOMOSCI_HISTORII = 40


def ogranicz_historie(
    historia: list[dict],
    limit: int = MAKSYMALNA_LICZBA_WIADOMOSCI_HISTORII,
) -> list[dict]:
    if limit <= 0:
        return []

    return historia[-limit:]


def wczytaj_historie(
    sciezka: Path = SCIEZKA_HISTORII,
    limit: int = MAKSYMALNA_LICZBA_WIADOMOSCI_HISTORII,
) -> list[dict]:
    if not sciezka.exists():
        return []

    try:
        with open(sciezka, "r", encoding="utf-8") as plik:
            historia = json.load(plik)
    except (json.JSONDecodeError, OSError):
        return []

    if not isinstance(historia, list):
        return []

    return ogranicz_historie(historia, limit)


def zapisz_historie(
    historia: list[dict],
    sciezka: Path = SCIEZKA_HISTORII,
    limit: int = MAKSYMALNA_LICZBA_WIADOMOSCI_HISTORII,
    sciezka_podsumowania: Path | None = None,
) -> None:
    sciezka.parent.mkdir(parents=True, exist_ok=True)
    if sciezka_podsumowania is not None and len(historia) > limit:
        _dopisz_podsumowanie_historii(
            historia[:-limit],
            sciezka_podsumowania,
        )
    historia_do_zapisu = ogranicz_historie(historia, limit)

    with open(sciezka, "w", encoding="utf-8") as plik:
        json.dump(historia_do_zapisu, plik, ensure_ascii=False, indent=4)


def wyczysc_historie(sciezka: Path = SCIEZKA_HISTORII) -> None:
    zapisz_historie([], sciezka)


def wczytaj_podsumowanie_historii(
    sciezka: Path = SCIEZKA_PODSUMOWANIA_HISTORII,
) -> str:
    if not sciezka.exists():
        return ""
    try:
        data = json.loads(sciezka.read_text(encoding="utf-8"))
    except (json.JSONDecodeError, OSError):
        return ""
    if isinstance(data, dict):
        return str(data.get("summary", "")).strip()
    return ""


def _dopisz_podsumowanie_historii(messages: list[dict[str, Any]], sciezka: Path) -> None:
    if not messages:
        return

    existing_summary = wczytaj_podsumowanie_historii(sciezka)
    new_lines = _zbuduj_podsumowanie_fragmentu(messages)
    summary_parts = [part for part in (existing_summary, new_lines) if part]
    summary = "\n".join(summary_parts)

    sciezka.parent.mkdir(parents=True, exist_ok=True)
    sciezka.write_text(
        json.dumps(
            {
                "updated_at": datetime.now().isoformat(timespec="seconds"),
                "summary": _limit_summary(summary),
            },
            ensure_ascii=False,
            indent=4,
        ),
        encoding="utf-8",
    )


def _zbuduj_podsumowanie_fragmentu(messages: list[dict[str, Any]]) -> str:
    lines = [f"Zarchiwizowano {len(messages)} starszych wiadomosci:"]
    for message in messages[-12:]:
        role = str(message.get("role", "unknown"))
        content = " ".join(str(message.get("content", "")).split())
        if content:
            lines.append(f"- {role}: {content[:180]}")
    return "\n".join(lines)


def _limit_summary(summary: str, max_chars: int = 6000) -> str:
    if len(summary) <= max_chars:
        return summary
    return summary[-max_chars:]
