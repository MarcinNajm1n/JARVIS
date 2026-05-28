from src.display.search_payload import extract_visual_assets, normalize_search_payload


def test_normalize_search_payload_results_format():
    payload = {
        "query": "openai",
        "results": [
            {
                "title": "OpenAI news",
                "summary": "Nowy wpis.",
                "url": "https://openai.com/news",
                "source": "OpenAI",
                "date": "2026-05-21",
                "score": 0.95,
            }
        ],
    }

    results = normalize_search_payload(payload)

    assert results[0]["title"] == "OpenAI news"
    assert results[0]["summary"] == "Nowy wpis."
    assert results[0]["url"] == "https://openai.com/news"
    assert results[0]["source"] == "OpenAI"
    assert results[0]["kind"] == "result"


def test_normalize_search_payload_answer_sources_format():
    payload = {
        "answer": "JARVIS znalazl dane.",
        "sources": [{"title": "Dokumentacja", "url": "https://example.com/docs"}],
    }

    results = normalize_search_payload(payload)

    assert results[0]["kind"] == "answer"
    assert results[0]["summary"] == "JARVIS znalazl dane."
    assert results[1]["kind"] == "source"
    assert results[1]["title"] == "Dokumentacja"


def test_normalize_search_payload_items_format():
    payload = {"items": [{"name": "Modul", "description": "Opis modulu.", "metadata": {"a": 1}}]}

    results = normalize_search_payload(payload)

    assert results[0]["title"] == "Modul"
    assert results[0]["summary"] == "Opis modulu."


def test_normalize_search_payload_graph_format():
    payload = {
        "nodes": [{"id": "a.md", "label": "A"}],
        "edges": [{"source": "a.md", "target": "b.md", "type": "link"}],
    }

    results = normalize_search_payload(payload)

    assert results[0]["kind"] == "node"
    assert results[1]["kind"] == "edge"


def test_normalize_search_payload_empty_payload_returns_diagnostic():
    results = normalize_search_payload({"foo": "bar"})

    assert results[0]["kind"] == "debug"
    assert results[0]["title"] == "NO SEARCH RESULTS RECEIVED"
    assert "no renderable fields" in results[0]["summary"]


def test_normalize_search_payload_preserves_image_url():
    payload = {
        "results": [
            {
                "title": "Visual result",
                "url": "https://example.com/article",
                "image_url": "https://cdn.example.com/hero.jpg",
            }
        ]
    }

    results = normalize_search_payload(payload)

    assert results[0]["imageUrl"] == "https://cdn.example.com/hero.jpg"
    assert results[0]["media"][0]["url"] == "https://cdn.example.com/hero.jpg"


def test_normalize_search_payload_preserves_thumbnail_url():
    payload = {"results": [{"title": "Thumb", "thumbnail_url": "https://cdn.example.com/thumb.webp"}]}

    results = normalize_search_payload(payload)

    assert results[0]["thumbnailUrl"] == "https://cdn.example.com/thumb.webp"
    assert results[0]["media"][0]["type"] == "image"


def test_extract_visual_assets_detects_images_collection():
    visual = extract_visual_assets({"images": [{"url": "https://cdn.example.com/a.png", "alt": "A"}]})

    assert visual["media"] == [{"type": "image", "url": "https://cdn.example.com/a.png", "alt": "A"}]


def test_extract_visual_assets_detects_media_collection():
    visual = extract_visual_assets({"media": [{"type": "image", "src": "https://cdn.example.com/b.jpg", "width": 640}]})

    assert visual["media"][0]["url"] == "https://cdn.example.com/b.jpg"
    assert visual["media"][0]["width"] == 640


def test_extract_visual_assets_generates_favicon_fallback_from_url():
    visual = extract_visual_assets({"url": "https://example.com/news/story"})

    assert visual["imageUrl"] == ""
    assert visual["faviconUrl"] == "https://www.google.com/s2/favicons?domain=example.com&sz=64"


def test_normalize_search_payload_does_not_stringify_source_as_object_object():
    payload = {"results": [{"title": "Source object", "source": {"title": "Docs", "url": "https://example.com/docs"}}]}

    results = normalize_search_payload(payload)

    assert results[0]["source"] == "Docs (example.com)"
    assert "[object Object]" not in results[0]["source"]
