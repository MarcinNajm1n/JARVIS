from __future__ import annotations

import re


MEMORY_PATTERNS = [
    r"\b(mam na imie .+)",
    r"\b(nazywam sie .+)",
    r"\b(studiuje .+)",
    r"\b(ucze sie .+)",
    r"\b(pracuje nad .+)",
    r"\b(buduje .+)",
    r"\b(moim celem jest .+)",
    r"\b(wole .+)",
    r"\b(preferuje .+)",
]


def extract_memory_candidate(text: str) -> str | None:
    normalized = " ".join(text.strip().split())
    if not normalized or normalized.startswith("/"):
        return None

    lowered = normalized.lower()
    for pattern in MEMORY_PATTERNS:
        match = re.search(pattern, lowered)
        if match:
            candidate = match.group(1).strip(" .")
            if len(candidate) >= 12:
                return candidate[0].upper() + candidate[1:] + "."

    return None
