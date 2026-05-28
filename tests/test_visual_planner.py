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
    assert payload["presentation"] == "animated_scene"
    assert payload["animation_profile"] == "result"
    assert "structured_data" not in payload
    assert payload["subject"] == "Elon Musk"
    assert payload["image_url"] == "https://example.com/elon.jpg"
    assert payload["sources"] == ["https://pl.wikipedia.org/wiki/Elon_Musk"]
    assert payload["cost"]["estimated_cost_usd"] == 0.0
    assert payload["planner_trace"]["selected_subject"] == "Elon Musk"
    assert payload["planner_trace"]["selection_source"] == "answer"
    assert payload["planner_trace"]["search_query"] == "Elon Musk"


def test_visual_planner_rachunki_generuja_structured_modal():
    payload = plan_visual_result(
        "pokaz moje rachunki za ten miesiac",
        "Prad 120,50 zl, termin 10.06.2026\nInternet 80 zl, platne 15.06.2026\nRazem 200,50 zl.",
        lookup=lambda _subject: None,
    )

    assert payload is not None
    assert payload["mode"] == "structured_table"
    assert payload["presentation"] == "structured_modal"
    assert payload["animation_profile"] == "result"
    assert payload["structured_data"]["columns"] == ["Pozycja", "Kwota", "Termin"]
    assert payload["structured_data"]["currency"] == "PLN"
    assert payload["structured_data"]["total"] == 200.5
    assert payload["structured_data"]["rows"][0]["item"] == "Prad"
    assert payload["structured_data"]["rows"][0]["amount"] == "120.50 PLN"


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


def test_visual_planner_tworzyl_research_brief_gdy_ma_search_bundle_z_mediami():
    bundle = WebSearchBundle(
        query="Elon Musk",
        results=[
            SearchResult(
                title="Elon Musk profile",
                url="https://example.com/1",
                snippet="Elon Musk jest przedsiebiorca.",
                image_url="https://example.com/1.jpg",
            ),
            SearchResult(
                title="Elon Musk companies",
                url="https://example.com/2",
                snippet="Elon Musk prowadzi firmy technologiczne.",
                image_url="https://example.com/2.jpg",
            ),
        ],
    )

    payload = plan_visual_result(
        "kto jest najbogatszy na swiecie",
        "Elon Musk jest przedsiebiorca.",
        lookup=lambda _subject: None,
        search_bundle=bundle,
    )

    assert payload["mode"] == "research_brief"
    assert payload["topic"] == "Elon Musk"
    assert len(payload["media_items"]) >= 2
    assert payload["validation"]["status"] == "supported"


def test_visual_planner_regresja_elon_nigdy_hansi_z_fake_search_bundle():
    bundle = WebSearchBundle(
        query="najbogatszy czlowiek",
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
        lookup=lambda _subject: None,
        web_search=lambda _query: bundle,
        search_bundle=bundle,
    )

    assert payload is not None
    assert payload["mode"] == "entity_profile"
    assert payload["subject"] == "Elon Musk"
    assert "Hansi" not in payload.get("title", "")
    assert not payload.get("media_items")


def test_visual_planner_nie_buduje_displaya_z_odpowiedzi_odmownej():
    answer = "Nie mam wystarczajaco pewnych aktualnych danych na podstawie podanych zrodel."

    payload = plan_visual_result(
        "kto jest najbogatszym czlowiekiem na swiecie",
        answer,
    )

    assert payload is None
    assert extract_visual_subject("kto jest najbogatszym czlowiekiem na swiecie", answer) is None


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
