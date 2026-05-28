from pathlib import Path

from src.elevenlabs_client import ElevenLabsVoiceClient


class Settings:
    elevenlabs_api_key = "eleven-key"
    elevenlabs_tts_enabled = True
    elevenlabs_stt_enabled = True
    elevenlabs_tts_model = "eleven_multilingual_v2"
    elevenlabs_stt_model = "scribe_v2"
    elevenlabs_voice_id = "voice-id"
    elevenlabs_output_format = "mp3_44100_128"
    elevenlabs_timeout_seconds = 1.0
    stt_language = "pl"


class FakeResponse:
    status_code = 200
    content = b"mp3"

    def __init__(self, payload=None):
        self._payload = payload or {"text": "Dzien dobry."}

    def raise_for_status(self):
        return None

    def json(self):
        return self._payload


def test_elevenlabs_tts_writes_audio(tmp_path: Path):
    calls = []

    class FakeClient:
        def post(self, url, **kwargs):
            calls.append((url, kwargs))
            return FakeResponse()

    output = tmp_path / "tts.mp3"
    result = ElevenLabsVoiceClient(Settings, client=FakeClient()).generate_speech("Test", output)

    assert result == output
    assert output.read_bytes() == b"mp3"
    assert "/text-to-speech/voice-id" in calls[0][0]
    assert calls[0][1]["json"]["model_id"] == "eleven_multilingual_v2"


def test_elevenlabs_stt_reads_text(tmp_path: Path):
    audio = tmp_path / "audio.wav"
    audio.write_bytes(b"wav")

    class FakeClient:
        def post(self, url, **kwargs):
            assert url.endswith("/speech-to-text")
            assert kwargs["data"]["model_id"] == "scribe_v2"
            return FakeResponse({"text": "Jarvis, sluchaj."})

    text = ElevenLabsVoiceClient(Settings, client=FakeClient()).transcribe_audio(audio)

    assert text == "Jarvis, sluchaj."
