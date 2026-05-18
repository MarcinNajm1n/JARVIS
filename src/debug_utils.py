from config import DEBUG


DEBUG_MODE = DEBUG


def debug_print(komunikat: str) -> None:
    if DEBUG_MODE:
        print(f"[DEBUG] {komunikat}")


def ustaw_debug(wartosc: bool) -> None:
    global DEBUG_MODE
    DEBUG_MODE = wartosc


def czy_debug_wlaczony() -> bool:
    return DEBUG_MODE
