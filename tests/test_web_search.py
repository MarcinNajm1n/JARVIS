from src import web_search
from src.web_search import search_web


def test_search_web_laczy_duckduckgo_i_wikipedie(monkeypatch):
    monkeypatch.setattr(web_search, "_search_forbes_realtime_billionaires", lambda query, timeout: [])

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


def test_search_web_uzywa_forbes_real_time_dla_najbogatszej_osoby(monkeypatch):
    html = """
    <html>
      <script id="__NEXT_DATA__" type="application/json">
        {"props":{"pageProps":{"data":{"billionairesData":{"billionaires":[
          {"rank":1,"personName":"Elon Musk","finalWorth":806458.451,
           "source":"Tesla, SpaceX","squareImage":"https://example.com/elon.jpg",
           "timestamp":1779307802117}
        ]}}}}}
      </script>
    </html>
    """

    class FakeResponse:
        def __enter__(self):
            return self

        def __exit__(self, exc_type, exc, tb):
            return False

        def read(self):
            return html.encode("utf-8")

    def fake_urlopen(request, timeout):
        return FakeResponse()

    monkeypatch.setattr(web_search.urllib.request, "urlopen", fake_urlopen)

    bundle = search_web("kto jest najbogatszym czlowiekiem na swiecie")

    assert bundle.best is not None
    assert bundle.best.title == "Forbes Real-Time Billionaires #1: Elon Musk"
    assert bundle.best.source == "Forbes Real-Time Billionaires"
    assert bundle.best.image_url == "https://example.com/elon.jpg"
