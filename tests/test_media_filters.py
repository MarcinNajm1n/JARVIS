from src.media_filters import (
    filter_images,
    filter_reports,
    filter_videos,
    image_candidates_from_search_results,
)
from src.research_models import ImageResult, ReportResult, ResearchFilters, VideoResult
from src.web_search import SearchResult


def test_filter_images_akceptuje_tylko_media_pasujace_do_tematu():
    filters = ResearchFilters(must_include=["Elon Musk"], entity_aliases=["Elon Musk", "Musk"])
    accepted = ImageResult(
        image_url="https://upload.wikimedia.org/elon.jpg",
        page_url="https://commons.wikimedia.org/wiki/Elon_Musk",
        caption="Elon Musk portrait",
        source="Wikimedia",
        width=1000,
        height=800,
    )
    rejected = ImageResult(
        image_url="https://example.com/hansi.jpg",
        page_url="https://example.com/hansi-flick",
        caption="Hansi Flick",
        source="web",
    )

    images = filter_images([rejected, accepted], filters)

    assert len(images) == 1
    assert images[0].image_url.endswith("elon.jpg")
    assert images[0].validation["status"] == "accepted"


def test_filter_reports_i_videos_sprawdzaja_tematyke_i_typ_zrodla():
    filters = ResearchFilters(must_include=["Oppenheimer"], entity_aliases=["Robert Oppenheimer", "Oppenheimer"])
    reports = filter_reports(
        [
            ReportResult(
                title="Robert Oppenheimer Manhattan Project report PDF",
                url="https://university.edu/oppenheimer.pdf",
                file_type="pdf",
            ),
            ReportResult(title="Hansi Flick profile", url="https://example.com/hansi"),
        ],
        filters,
    )
    videos = filter_videos(
        [
            VideoResult(
                title="Robert Oppenheimer documentary",
                url="https://youtube.com/watch?v=test",
                source="YouTube",
            ),
            VideoResult(title="Random football video", url="https://youtube.com/watch?v=bad"),
        ],
        filters,
    )

    assert reports[0].url.endswith(".pdf")
    assert reports[0].confidence >= 0.6
    assert videos[0].title == "Robert Oppenheimer documentary"
    assert len(videos) == 1


def test_image_candidates_from_search_results_nie_tworzacy_falszywych_obrazow():
    candidates = image_candidates_from_search_results(
        [
            SearchResult(title="Elon Musk", url="https://example.com/elon", image_url="https://example.com/e.jpg"),
            SearchResult(title="No image", url="https://example.com/no-image"),
        ]
    )

    assert len(candidates) == 1
    assert candidates[0].caption == "Elon Musk"
