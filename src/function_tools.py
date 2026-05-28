from __future__ import annotations

import json
from dataclasses import dataclass
from datetime import datetime
from pathlib import Path
from typing import Any

from src.command_catalog import search_command_catalog
from src.json_store import read_json, write_json
from src.long_term_memory import (
    dodaj_wpis_pamieci,
    edytuj_wpis_pamieci,
    formatuj_memory_review,
    szukaj_pamieci,
    usun_wpis_pamieci,
    zapisz_pamiec_stala,
)
from src.response_modes import list_modes
from src.weather_service import get_current_weather


RISK_SAFE = "safe"
RISK_REQUIRES_CONFIRMATION = "requires_confirmation"
RISK_DANGEROUS = "dangerous"


JARVIS_FUNCTION_TOOLS: list[dict[str, Any]] = [
    {
        "type": "function",
        "name": "add_task",
        "description": "Dodaje nowe zadanie do lokalnej listy zadan JARVISA.",
        "parameters": {
            "type": "object",
            "properties": {
                "title": {
                    "type": "string",
                    "description": "Krotki, konkretny opis zadania do zapisania.",
                }
            },
            "required": ["title"],
            "additionalProperties": False,
        },
        "strict": True,
    },
    {
        "type": "function",
        "name": "list_tasks",
        "description": "Pobiera lokalna liste zadan uzytkownika.",
        "parameters": {
            "type": "object",
            "properties": {
                "include_done": {
                    "type": "boolean",
                    "description": "Czy pokazac rowniez zadania juz wykonane.",
                }
            },
            "required": ["include_done"],
            "additionalProperties": False,
        },
        "strict": True,
    },
    {
        "type": "function",
        "name": "mark_task_done",
        "description": "Oznacza lokalne zadanie jako wykonane.",
        "parameters": {
            "type": "object",
            "properties": {
                "task_id": {
                    "type": "integer",
                    "description": "Identyfikator zadania do oznaczenia jako wykonane.",
                }
            },
            "required": ["task_id"],
            "additionalProperties": False,
        },
        "strict": True,
    },
    {
        "type": "function",
        "name": "remove_task",
        "description": "Usuwa zadanie po jawnym potwierdzeniu uzytkownika.",
        "parameters": {
            "type": "object",
            "properties": {
                "task_id": {
                    "type": "integer",
                    "description": "Identyfikator zadania do usuniecia.",
                },
                "confirmation": {
                    "type": "string",
                    "description": "Wymagane dokladne potwierdzenie: potwierdzam.",
                },
            },
            "required": ["task_id", "confirmation"],
            "additionalProperties": False,
        },
        "strict": True,
    },
    {
        "type": "function",
        "name": "get_profile",
        "description": "Pobiera lokalny profil uzytkownika.",
        "parameters": {
            "type": "object",
            "properties": {},
            "required": [],
            "additionalProperties": False,
        },
        "strict": True,
    },
    {
        "type": "function",
        "name": "set_profile_value",
        "description": "Aktualizuje pojedyncze pole lokalnego profilu uzytkownika.",
        "parameters": {
            "type": "object",
            "properties": {
                "key": {
                    "type": "string",
                    "description": "Nazwa pola profilu, np. name, field albo response_style.",
                },
                "value": {
                    "type": "string",
                    "description": "Nowa wartosc pola profilu.",
                },
            },
            "required": ["key", "value"],
            "additionalProperties": False,
        },
        "strict": True,
    },
    {
        "type": "function",
        "name": "get_project_status",
        "description": "Pobiera status aktywnego projektu albo wskazanego projektu.",
        "parameters": {
            "type": "object",
            "properties": {
                "project_name": {
                    "type": "string",
                    "description": "Nazwa projektu albo pusty string dla aktywnego projektu.",
                }
            },
            "required": ["project_name"],
            "additionalProperties": False,
        },
        "strict": True,
    },
    {
        "type": "function",
        "name": "set_active_project",
        "description": "Ustawia aktywny projekt i tworzy go lokalnie, jesli jeszcze nie istnieje.",
        "parameters": {
            "type": "object",
            "properties": {
                "project_name": {
                    "type": "string",
                    "description": "Nazwa projektu, ktory ma stac sie aktywny.",
                }
            },
            "required": ["project_name"],
            "additionalProperties": False,
        },
        "strict": True,
    },
    {
        "type": "function",
        "name": "add_project_note",
        "description": "Dodaje notatke do aktualnie aktywnego projektu.",
        "parameters": {
            "type": "object",
            "properties": {
                "note": {
                    "type": "string",
                    "description": "Konkretna notatka projektowa do zapisania.",
                }
            },
            "required": ["note"],
            "additionalProperties": False,
        },
        "strict": True,
    },
    {
        "type": "function",
        "name": "set_response_mode",
        "description": "Zmienia tryb odpowiedzi JARVISA.",
        "parameters": {
            "type": "object",
            "properties": {
                "mode": {
                    "type": "string",
                    "enum": list_modes(),
                    "description": "Docelowy tryb odpowiedzi.",
                }
            },
            "required": ["mode"],
            "additionalProperties": False,
        },
        "strict": True,
    },
    {
        "type": "function",
        "name": "add_memory_fact",
        "description": "Dodaje potwierdzony wpis do pamieci stalej uzytkownika z typem.",
        "parameters": {
            "type": "object",
            "properties": {
                "fact": {
                    "type": "string",
                    "description": "Fakt o uzytkowniku, projekcie lub preferencjach.",
                },
                "memory_type": {
                    "type": "string",
                    "enum": ["profile", "preferences", "projects", "facts", "decisions"],
                    "description": "Typ pamieci.",
                }
            },
            "required": ["fact", "memory_type"],
            "additionalProperties": False,
        },
        "strict": True,
    },
    {
        "type": "function",
        "name": "search_memory",
        "description": "Wyszukuje wpisy w pamieci stalej JARVISA.",
        "parameters": {
            "type": "object",
            "properties": {
                "query": {
                    "type": "string",
                    "description": "Szukana informacja.",
                }
            },
            "required": ["query"],
            "additionalProperties": False,
        },
        "strict": True,
    },
    {
        "type": "function",
        "name": "edit_memory",
        "description": "Edytuje wpis pamieci po potwierdzeniu uzytkownika.",
        "parameters": {
            "type": "object",
            "properties": {
                "memory_id": {"type": "integer", "description": "Id wpisu pamieci."},
                "content": {"type": "string", "description": "Nowa tresc wpisu."},
                "memory_type": {
                    "type": "string",
                    "enum": ["profile", "preferences", "projects", "facts", "decisions"],
                    "description": "Nowy typ pamieci.",
                },
                "confirmation": {
                    "type": "string",
                    "description": "Wymagane dokladne potwierdzenie: potwierdzam.",
                },
            },
            "required": ["memory_id", "content", "memory_type", "confirmation"],
            "additionalProperties": False,
        },
        "strict": True,
    },
    {
        "type": "function",
        "name": "remove_memory",
        "description": "Usuwa wpis pamieci po potwierdzeniu uzytkownika.",
        "parameters": {
            "type": "object",
            "properties": {
                "memory_id": {"type": "integer", "description": "Id wpisu pamieci."},
                "confirmation": {
                    "type": "string",
                    "description": "Wymagane dokladne potwierdzenie: potwierdzam.",
                },
            },
            "required": ["memory_id", "confirmation"],
            "additionalProperties": False,
        },
        "strict": True,
    },
    {
        "type": "function",
        "name": "clear_memory",
        "description": "Czyści cala pamiec stala. Operacja niebezpieczna, wymaga mocnego potwierdzenia.",
        "parameters": {
            "type": "object",
            "properties": {
                "confirmation": {
                    "type": "string",
                    "description": "Wymagane dokladne potwierdzenie: potwierdzam wyczysc pamiec.",
                }
            },
            "required": ["confirmation"],
            "additionalProperties": False,
        },
        "strict": True,
    },
    {
        "type": "function",
        "name": "search_commands",
        "description": "Wyszukuje lokalne komendy JARVISA pasujace do pytania uzytkownika.",
        "parameters": {
            "type": "object",
            "properties": {
                "query": {
                    "type": "string",
                    "description": "Pytanie albo opis akcji, np. jak moge cie wylaczyc.",
                }
            },
            "required": ["query"],
            "additionalProperties": False,
        },
        "strict": True,
    },
    {
        "type": "function",
        "name": "get_weather",
        "description": "Pobiera aktualna pogode dla wskazanej lokalizacji i zwraca dane do panelu wizualnego.",
        "parameters": {
            "type": "object",
            "properties": {
                "location": {
                    "type": "string",
                    "description": "Miasto albo lokalizacja, np. Berlin.",
                }
            },
            "required": ["location"],
            "additionalProperties": False,
        },
        "strict": True,
    },
]


JARVIS_TOOL_RISK: dict[str, str] = {
    "add_task": RISK_SAFE,
    "list_tasks": RISK_SAFE,
    "mark_task_done": RISK_SAFE,
    "remove_task": RISK_REQUIRES_CONFIRMATION,
    "get_profile": RISK_SAFE,
    "set_profile_value": RISK_SAFE,
    "get_project_status": RISK_SAFE,
    "set_active_project": RISK_SAFE,
    "add_project_note": RISK_SAFE,
    "set_response_mode": RISK_SAFE,
    "add_memory_fact": RISK_SAFE,
    "search_memory": RISK_SAFE,
    "edit_memory": RISK_REQUIRES_CONFIRMATION,
    "remove_memory": RISK_REQUIRES_CONFIRMATION,
    "clear_memory": RISK_DANGEROUS,
    "search_commands": RISK_SAFE,
    "get_weather": RISK_SAFE,
}


@dataclass
class JarvisToolContext:
    assistant_state: Any
    profile_store: Any
    task_store: Any
    project_store: Any
    long_term_memory: list[Any]
    long_term_memory_path: Any = None
    tool_call_log_path: Any = None


def execute_jarvis_tool(
    name: str,
    arguments: dict[str, Any],
    context: JarvisToolContext,
) -> str:
    risk = JARVIS_TOOL_RISK.get(name, RISK_DANGEROUS)
    try:
        confirmation_result = _validate_tool_confirmation(name, arguments, risk)
        if confirmation_result is not None:
            _log_tool_call(
                context,
                name=name,
                risk=risk,
                arguments=arguments,
                status="confirmation_required",
                result=confirmation_result,
            )
            return json.dumps(
                {"ok": False, "confirmation_required": True, "result": confirmation_result},
                ensure_ascii=False,
            )

        result = _execute_known_tool(name, arguments, context)
        _log_tool_call(
            context,
            name=name,
            risk=risk,
            arguments=arguments,
            status="ok",
            result=result,
        )
        return json.dumps({"ok": True, "result": result}, ensure_ascii=False)
    except Exception as error:
        _log_tool_call(
            context,
            name=name,
            risk=risk,
            arguments=arguments,
            status="error",
            result={"error": str(error)},
        )
        return json.dumps(
            {
                "ok": False,
                "error": str(error),
                "tool": name,
            },
            ensure_ascii=False,
        )


def _execute_known_tool(
    name: str,
    arguments: dict[str, Any],
    context: JarvisToolContext,
) -> dict[str, Any]:
    if name == "add_task":
        title = _require_text(arguments, "title")
        task = context.task_store.add(title)
        return {"message": "Dodano zadanie.", "task": task}

    if name == "list_tasks":
        include_done = bool(arguments.get("include_done", True))
        return {"tasks": context.task_store.list(include_done=include_done)}

    if name == "mark_task_done":
        task_id = int(arguments.get("task_id", -1))
        changed = context.task_store.mark_done(task_id)
        if not changed:
            raise ValueError(f"Nie znaleziono zadania #{task_id}.")
        return {"message": "Oznaczono zadanie jako wykonane.", "task_id": task_id}

    if name == "remove_task":
        task_id = int(arguments.get("task_id", -1))
        changed = context.task_store.remove(task_id)
        if not changed:
            raise ValueError(f"Nie znaleziono zadania #{task_id}.")
        return {"message": "Usunieto zadanie.", "task_id": task_id}

    if name == "get_profile":
        return {"profile": context.profile_store.get()}

    if name == "set_profile_value":
        key = _require_text(arguments, "key")
        value = _require_text(arguments, "value")
        context.profile_store.set_value(key, value)
        return {"message": "Zaktualizowano profil.", "key": key, "value": value}

    if name == "set_active_project":
        project_name = _require_text(arguments, "project_name")
        context.project_store.ensure_project(project_name)
        context.assistant_state.set_active_project(project_name)
        return {"message": "Ustawiono aktywny projekt.", "project_name": project_name}

    if name == "get_project_status":
        project_name = str(arguments.get("project_name", "")).strip()
        active_project = context.assistant_state.get_active_project()
        return {
            "active_project": active_project,
            "status": context.project_store.summarize(project_name or active_project),
        }

    if name == "add_project_note":
        note = _require_text(arguments, "note")
        active_project = context.assistant_state.get_active_project()
        if not active_project:
            raise ValueError("Brak aktywnego projektu. Najpierw ustaw projekt.")
        context.project_store.add_note(active_project, note)
        return {"message": "Dodano notatke do projektu.", "project_name": active_project}

    if name == "set_response_mode":
        mode = _require_text(arguments, "mode").lower()
        if mode not in list_modes():
            raise ValueError(f"Nieznany tryb odpowiedzi: {mode}")
        context.assistant_state.set_response_mode(mode)
        return {"message": "Zmieniono tryb odpowiedzi.", "mode": mode}

    if name == "add_memory_fact":
        fact = _require_text(arguments, "fact")
        memory_type = _require_text(arguments, "memory_type")
        entry = dodaj_wpis_pamieci(context.long_term_memory, fact, memory_type)
        _save_memory_if_configured(context)
        return {
            "message": "Zapisano fakt w pamieci stalej.",
            "fact": fact,
            "entry": entry,
            "added": entry is not None,
        }

    if name == "search_memory":
        query = _require_text(arguments, "query")
        return {"matches": szukaj_pamieci(context.long_term_memory, query)}

    if name == "edit_memory":
        memory_id = int(arguments.get("memory_id", -1))
        content = _require_text(arguments, "content")
        memory_type = _require_text(arguments, "memory_type")
        entry = edytuj_wpis_pamieci(context.long_term_memory, memory_id, content, memory_type)
        if entry is None:
            raise ValueError(f"Nie znaleziono wpisu pamieci #{memory_id}.")
        _save_memory_if_configured(context)
        return {"message": "Zaktualizowano wpis pamieci.", "entry": entry}

    if name == "remove_memory":
        memory_id = int(arguments.get("memory_id", -1))
        removed = usun_wpis_pamieci(context.long_term_memory, memory_id)
        if not removed:
            raise ValueError(f"Nie znaleziono wpisu pamieci #{memory_id}.")
        _save_memory_if_configured(context)
        return {"message": "Usunieto wpis pamieci.", "memory_id": memory_id}

    if name == "clear_memory":
        context.long_term_memory[:] = []
        _save_memory_if_configured(context)
        return {"message": "Wyczyszczono pamiec stala."}

    if name == "search_commands":
        query = _require_text(arguments, "query")
        return {"commands": search_command_catalog(query)}

    if name == "get_weather":
        location = _require_text(arguments, "location")
        return get_current_weather(location).to_visual_payload()

    raise ValueError(f"Nieznane narzedzie: {name}")


def _require_text(arguments: dict[str, Any], key: str) -> str:
    value = str(arguments.get(key, "")).strip()
    if not value:
        raise ValueError(f"Brakuje wymaganego argumentu: {key}")
    return value


def _save_memory_if_configured(context: JarvisToolContext) -> None:
    if context.long_term_memory_path is not None:
        zapisz_pamiec_stala(context.long_term_memory, Path(context.long_term_memory_path))


def _validate_tool_confirmation(
    name: str,
    arguments: dict[str, Any],
    risk: str,
) -> dict[str, Any] | None:
    if risk == RISK_SAFE:
        return None

    confirmation = str(arguments.get("confirmation", "")).strip().lower()
    required = "potwierdzam wyczysc pamiec" if risk == RISK_DANGEROUS else "potwierdzam"
    if confirmation == required:
        return None

    return {
        "message": "Ta operacja wymaga jawnego potwierdzenia.",
        "tool": name,
        "risk": risk,
        "required_confirmation": required,
    }


def _log_tool_call(
    context: JarvisToolContext,
    name: str,
    risk: str,
    arguments: dict[str, Any],
    status: str,
    result: dict[str, Any],
) -> None:
    if context.tool_call_log_path is None:
        return
    path = Path(context.tool_call_log_path)
    entries = read_json(path, [])
    if not isinstance(entries, list):
        entries = []
    entries.append(
        {
            "created_at": datetime.now().isoformat(timespec="seconds"),
            "tool": name,
            "risk": risk,
            "arguments": _redact_sensitive(arguments),
            "status": status,
            "result": _redact_sensitive(result),
        }
    )
    write_json(path, entries[-200:])


def _redact_sensitive(value: Any) -> Any:
    if isinstance(value, dict):
        redacted: dict[str, Any] = {}
        for key, nested_value in value.items():
            if _is_sensitive_key(str(key)):
                redacted[key] = "***"
            else:
                redacted[key] = _redact_sensitive(nested_value)
        return redacted
    if isinstance(value, list):
        return [_redact_sensitive(item) for item in value]
    return value


def _is_sensitive_key(key: str) -> bool:
    normalized = key.lower()
    sensitive_markers = (
        "api_key",
        "apikey",
        "secret",
        "token",
        "password",
        "passwd",
        "pwd",
        "credential",
        "authorization",
        "cookie",
        "confirmation",
    )
    return any(marker in normalized for marker in sensitive_markers)
