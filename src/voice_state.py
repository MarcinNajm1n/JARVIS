from src.config import load_settings


_voice_enabled = load_settings().tts_enabled


def czy_mowa_wlaczona() -> bool:
    return _voice_enabled


def ustaw_mowe(wartosc: bool) -> None:
    global _voice_enabled
    _voice_enabled = wartosc
