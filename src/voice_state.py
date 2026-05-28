from src.config import load_settings


_settings = load_settings()
_voice_enabled = _settings.tts_enabled
_voice_provider = _settings.voice_provider if _settings.voice_provider in {"openai", "elevenlabs"} else "openai"


def czy_mowa_wlaczona() -> bool:
    return _voice_enabled


def ustaw_mowe(wartosc: bool) -> None:
    global _voice_enabled
    _voice_enabled = wartosc


def aktywny_provider_glosu() -> str:
    return _voice_provider


def ustaw_provider_glosu(provider: str) -> bool:
    global _voice_provider
    normalized = (provider or "").strip().lower()
    aliases = {
        "openai": "openai",
        "default": "openai",
        "standard": "openai",
        "jarvis": "openai",
        "elevenlabs": "elevenlabs",
        "eleven": "elevenlabs",
        "11labs": "elevenlabs",
    }
    if normalized not in aliases:
        return False
    _voice_provider = aliases[normalized]
    return True
