from src.research_query_planner import plan_queries


def test_query_planner_preferuje_encje_z_odpowiedzi_llm():
    plan = plan_queries(
        "kto jest najbogatszy na swiecie",
        "Wedlug najnowszych rankingow Elon Musk jest na szczycie listy.",
    )

    assert plan.topic == "Elon Musk"
    assert plan.freshness_required is True
    assert plan.intent == "entity_research"
    assert plan.web_queries[0] == "Elon Musk"
    assert "Elon Musk" in plan.filters.must_include
    assert "Musk" in plan.filters.entity_aliases


def test_query_planner_ma_specjalny_plan_dla_aktualnego_rankingu_najbogatszych():
    plan = plan_queries("kto jest najbogatszym czlowiekiem na swiecie", "")

    assert plan.intent == "current_ranking"
    assert plan.topic == "richest person in the world"
    assert plan.freshness_required is True
    assert plan.web_queries[0].startswith("Forbes Real-Time Billionaires")
    assert "forbes.com" in plan.filters.preferred_domains
    assert "bloomberg.com" in plan.filters.preferred_domains


def test_query_planner_buduje_osobne_query_dla_mediow():
    plan = plan_queries("kim jest Robert Oppenheimer?", "")

    assert plan.topic == "Robert Oppenheimer"
    assert any("portrait" in query for query in plan.image_queries)
    assert any("PDF" in query for query in plan.report_queries)
    assert any("documentary" in query for query in plan.video_queries)
