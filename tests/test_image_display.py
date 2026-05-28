from src.image_display import prepare_display_images, validate_image_display
from src.research_models import ImageResult


def test_prepare_display_images_wymusza_contain_i_brak_przycinania():
    image = ImageResult(
        image_url="https://upload.wikimedia.org/elon.jpg",
        page_url="https://commons.wikimedia.org/wiki/Elon_Musk",
        caption="Elon Musk portrait",
        source="Wikimedia",
        confidence=0.9,
        validation={"status": "accepted"},
    )

    prepared = prepare_display_images([image], "Elon Musk")

    assert len(prepared) == 1
    assert prepared[0].validation["display"]["fit"] == "contain"
    assert prepared[0].validation["display"]["cropping_allowed"] is False
    assert prepared[0].validation["display_validation"]["visible_subject_expected"] is True


def test_validate_image_display_odrzuca_zdjecie_innego_tematu():
    image = ImageResult(
        image_url="https://example.com/hansi.jpg",
        page_url="https://example.com/hansi-flick",
        caption="Hansi Flick",
    )

    validation = validate_image_display(image, "Elon Musk")

    assert validation["status"] == "rejected"
    assert validation["reason"] == "image_topic_mismatch"
