from src import web_search
from src.web_search import search_web


def test_search_web_laczy_duckduckgo_i_wikipedie(monkeypatch):
    def fake_fetch_json(url, timeout):
        if "api.duckduckgo.com" in url:
            return {
                "Heading": "Elon Musk",
                "AbstractText": "Elon Musk jest przedsiebiorca.",
                "AbstractURL": "https://example.com/elon",
                "Image": "/i/elon.jpg",
                "RelatedTopics": [],
            }
        return {
            "query": {
                "search": [
                    {
                        "title": "Elon Musk",
                        "snippet": "amerykanski przedsiebiorca",
                    }
                ]
            }
        }

    monkeypatch.setattr(web_search, "_fetch_json", fake_fetch_json)

    bundle = search_web("kto jest najbogatszy na swiecie")

    assert bundle.best is not None
    assert bundle.best.title == "Elon Musk"
    assert bundle.best.image_url == "https://duckduckgo.com/i/elon.jpg"
    assert bundle.results[0].source == "DuckDuckGo"
