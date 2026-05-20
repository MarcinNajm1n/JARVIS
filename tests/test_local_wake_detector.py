from src.local_wake_detector import LocalWakeDetector
from src.stt import SpeechToTextClient


def test_local_wake_detector_rozpoznaje_aktywacje_z_intencji():
    detector = LocalWakeDetector(SpeechToTextClient())

    result = detector.detect_from_text("jarvis aktywacja")

    assert result.activated is True
    assert result.method == "local_intent"
    assert result.confidence >= 0.9


def test_local_wake_detector_odrzuca_zwykly_tekst():
    detector = LocalWakeDetector(SpeechToTextClient())

    result = detector.detect_from_text("dodaj zadanie do projektu")

    assert result.activated is False
