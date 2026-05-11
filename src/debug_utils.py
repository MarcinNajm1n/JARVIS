from config import DEBUG


def debug_print(komunikat: str) -> None:
    if DEBUG:
        print(f"[DEBUG] {komunikat}")