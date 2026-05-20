from dataclasses import replace
from types import SimpleNamespace

from src.config import load_settings
from src.cost_tracker import CostTracker, extract_response_usage


def test_cost_tracker_liczy_koszt_gpt_4_1_mini_i_zapisuje_sumy(tmp_path):
    settings = replace(load_settings(), cost_log_path=tmp_path / "usage_costs.json")
    tracker = CostTracker(settings)

    record = tracker.record_llm_usage(
        model="gpt-4.1-mini",
        input_tokens=1000,
        output_tokens=500,
        source="test",
    )

    assert record.estimated_cost_usd == 0.0012
    snapshot = CostTracker(settings).snapshot()
    assert snapshot["input_tokens"] == 1000
    assert snapshot["output_tokens"] == 500
    assert snapshot["estimated_cost_usd"] == 0.0012


def test_extract_response_usage_obsluguje_responses_api_usage():
    response = SimpleNamespace(
        usage=SimpleNamespace(input_tokens=321, output_tokens=123)
    )

    assert extract_response_usage(response) == (321, 123)
