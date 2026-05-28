from src.retrieval.models import SearchMode
from src.retrieval.router import QueryRouter


def test_query_router_news_dzisiaj():
    plan = QueryRouter().plan("co sie dzisiaj wydarzylo w OpenAI?")

    assert plan.needs_realtime is True
    assert plan.mode == SearchMode.NEWS


def test_query_router_stable_question_without_realtime():
    plan = QueryRouter().plan("jak dziala fotosynteza")

    assert plan.needs_realtime is False
    assert plan.mode == SearchMode.NONE


def test_query_router_software_release():
    plan = QueryRouter().plan("jaka jest najnowsza wersja FastAPI")

    assert plan.needs_realtime is True
    assert plan.mode == SearchMode.SOFTWARE
    assert any("official" in query for query in plan.search_queries)


def test_query_router_high_risk_requires_three_sources():
    plan = QueryRouter().plan("kto jest obecnie prezydentem i co zmienila nowa ustawa?")

    assert plan.mode == SearchMode.HIGH_RISK
    assert plan.min_sources == 3
