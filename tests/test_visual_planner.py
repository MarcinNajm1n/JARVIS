from src.visual_planner import EntityProfile, extract_visual_subject, plan_visual_result
from src.web_search import SearchResult, WebSearchBundle


def test_visual_planner_generuje_entity_profile_dla_dowolnego_pytania_faktograficznego():
    def fake_lookup(subject):
        assert subject == "Elon Musk"
        return EntityProfile(
            title="Elon Musk",
            summary="Elon Musk jest przedsiebiorca i zalozycielem kilku firm.",
            image_url="https://example.com/elon.jpg",
            source_url="https://pl.wikipedia.org/wiki/Elon_Musk",
            facts=["Zalozyl SpaceX.", "Kieruje Tesla."],
        )

    payload = plan_visual_result(
        "kto jest najbogatszy na swiecie",
        "Elon Musk jest czesto wymieniany jako jedna z najbogatszych osob na swiecie.",
        lookup=fake_lookup,
    )

    assert payload is not None
    assert payload["type"] == "visual_result"
    assert payload["mode"] == "entity_profile"
    assert payload["subject"] == "Elon Musk"
    assert payload["image_url"] == "https://example.com/elon.jpg"
    assert payload["sources"] == ["https://pl.wikipedia.org/wiki/Elon_Musk"]
    assert payload["cost"]["estimated_cost_usd"] == 0.0
    assert payload["planner_trace"]["selected_subject"] == "Elon Musk"
    assert payload["planner_trace"]["selection_source"] == "answer"
    assert payload["planner_trace"]["search_query"] == "Elon Musk"


def test_visual_planner_uzywa_web_search_gdy_wikipedia_nie_trafia():
    queries = []

    def fake_search(query):
        queries.append(query)
        return WebSearchBundle(
            query=query,
            results=[
                SearchResult(
                    title="Elon Musk",
                    url="https://example.com/elon",
                    snippet="Elon Musk jest przedsiebiorca.",
                    image_url="https://example.com/elon.jpg",
                    source="Search",
                )
            ],
        )

    payload = plan_visual_result(
        "kto jest najbogatszy na swiecie",
        "Elon Musk jest przedsiebiorca.",
        lookup=lambda _subject: None,
        web_search=fake_search,
    )

    assert payload is not None
    assert payload["mode"] == "entity_profile"
    assert payload["subject"] == "Elon Musk"
    assert payload["image_url"] == "https://example.com/elon.jpg"
    assert payload["related_results"][0]["title"] == "Elon Musk"
    assert queries == ["Elon Musk"]


def test_visual_planner_blokuje_display_gdy_search_zwraca_inna_encje():
    def fake_lookup(subject):
        assert subject == "Elon Musk"
        return EntityProfile(
            title="Hansi Flick",
            summary="Hans-Dieter Flick jest niemieckim trenerem pilkarskim.",
            image_url="https://example.com/hansi.jpg",
            source_url="https://pl.wikipedia.org/wiki/Hansi_Flick",
        )

    def fake_search(query):
        assert query == "Elon Musk"
        return WebSearchBundle(
            query=query,
            results=[
                SearchResult(
                    title="Hansi Flick",
                    url="https://pl.wikipedia.org/wiki/Hansi_Flick",
                    snippet="Hans-Dieter Flick jest niemieckim trenerem pilkarskim.",
                    image_url="https://example.com/hansi.jpg",
                    source="Wikipedia",
                )
            ],
        )

    payload = plan_visual_result(
        "Pokaz mi, kto jest najbogatszym czlowiekiem na swiecie.",
        "Wedlug magazynu Forbes, Elon Musk jest obecnie najbogatszym czlowiekiem na swiecie.",
        lookup=fake_lookup,
        web_search=fake_search,
    )

    assert payload is not None
    assert payload["mode"] == "generic"
    assert payload["ok"] is False
    assert payload["title"] == "Brak pewnego displaya"
    assert payload["subject"] == "Elon Musk"
    assert payload["planner_trace"]["rejected_subject"] == "Hansi Flick"
    assert payload["planner_trace"]["validation"] == "profile_title_mismatch"
    assert "Hansi" not in payload["summary"]


def test_visual_planner_nie_duplikuje_dedykowanego_displayu_pogody():
    payload = plan_visual_result(
        "jaka jest pogoda w Berlinie",
        "Berlin: 18 stopni i zachmurzenie.",
        lookup=lambda _subject: None,
    )

    assert payload is None


def test_visual_planner_wyciaga_temat_z_pytania_albo_odpowiedzi():
    assert extract_visual_subject("kim jest Ada Lovelace?", "") == "Ada Lovelace"
    assert extract_visual_subject(
        "kto jest najbogatszy na swiecie?",
        "Elon Musk jest przedsiebiorca.",
    ) == "Elon Musk"
    assert extract_visual_subject(
        "kto jest najbogatszy na swiecie?",
        "Wedlug Forbes Elon Musk jest najbogatsza osoba.",
    ) == "Elon Musk"
