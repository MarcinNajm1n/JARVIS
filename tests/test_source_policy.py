from src.retrieval.models import QueryPlan, SearchMode, SearchResult
from src.retrieval.router import QueryRouter
from src.retrieval.source_policy import enrich_plan_with_source_policy, filter_search_results


def test_high_risk_president_query_uses_official_domains_and_blocks_social():
    plan = enrich_plan_with_source_policy(
        QueryRouter().plan("Kto jest obecnie prezydentem Stanow Zjednoczonych?")
    )

    assert plan.mode == SearchMode.HIGH_RISK
    assert "whitehouse.gov" in plan.required_domains
    assert "facebook.com" in plan.excluded_domains
    assert plan.requires_official_source is True
    assert any("whitehouse.gov" in query for query in plan.search_queries)


def test_source_policy_rejects_facebook_for_high_risk_before_fetch():
    plan = enrich_plan_with_source_policy(
        QueryRouter().plan("Kto jest prezydentem Stanow Zjednoczonych?")
    )
    accepted, decisions = filter_search_results(
        [
            SearchResult(
                title="Facebook post",
                url="https://www.facebook.com/example/posts/123",
                snippet="Donald Trump president.",
                provider="tavily",
            ),
            SearchResult(
                title="The White House",
                url="https://www.whitehouse.gov/administration/",
                snippet="Official administration page.",
                provider="tavily",
            ),
        ],
        plan,
    )

    assert [result.url for result in accepted] == ["https://www.whitehouse.gov/administration/"]
    assert any(decision.status == "rejected_social" for decision in decisions)


def test_richest_person_prefers_forbes_bloomberg_reuters_not_random_wikipedia():
    plan = enrich_plan_with_source_policy(
        QueryRouter().plan("Kto jest najbogatszym czlowiekiem na swiecie?")
    )
    accepted, decisions = filter_search_results(
        [
            SearchResult(
                title="Random biography",
                url="https://pl.wikipedia.org/wiki/Jan_Kowalski",
                snippet="Pisarz.",
                provider="tavily",
            ),
            SearchResult(
                title="Forbes Real Time Billionaires",
                url="https://www.forbes.com/real-time-billionaires/",
                snippet="The richest people in the world.",
                provider="tavily",
            ),
        ],
        plan,
    )

    assert plan.mode == SearchMode.FINANCE
    assert [result.url for result in accepted] == ["https://www.forbes.com/real-time-billionaires/"]
    assert any(decision.status == "rejected_wrong_domain" for decision in decisions)
