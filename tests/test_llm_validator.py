from src.llm_validator import validate_research_brief
from src.research_models import ImageResult, ValidatedEvidence, VisualBrief


def test_llm_validator_lokalnie_odrzuca_media_gdy_temat_nie_jest_w_odpowiedzi():
    brief = VisualBrief(
        topic="Hansi Flick",
        title="Hansi Flick",
        summary="Profil Hansi Flick.",
        confidence=0.7,
        images=[
            ImageResult(
                image_url="https://example.com/hansi.jpg",
                page_url="https://example.com/hansi",
                caption="Hansi Flick",
            )
        ],
        sources=["https://example.com/hansi"],
    )

    validation = validate_research_brief(
        "kto jest najbogatszy na swiecie",
        "Elon Musk jest najbogatszym czlowiekiem w tej odpowiedzi.",
        brief,
    )

    assert validation["status"] == "rejected"
    assert validation["topic_seen_in_answer_or_question"] is False


def test_llm_validator_akceptuje_spojny_display_z_evidence():
    brief = VisualBrief(
        topic="Elon Musk",
        title="Elon Musk",
        summary="Elon Musk jest przedsiebiorca.",
        confidence=0.8,
        images=[
            ImageResult(
                image_url="https://example.com/elon.jpg",
                page_url="https://example.com/elon",
                caption="Elon Musk",
            )
        ],
        evidence=[
            ValidatedEvidence(
                claim="Elon Musk jest przedsiebiorca.",
                source_url="https://example.com/elon",
                source_title="Elon Musk",
                confidence=0.8,
            )
        ],
        sources=["https://example.com/elon"],
    )

    validation = validate_research_brief(
        "kto jest najbogatszy na swiecie",
        "Elon Musk jest jedna z najbogatszych osob.",
        brief,
    )

    assert validation["status"] == "accepted"
    assert validation["confidence"] >= 0.64
