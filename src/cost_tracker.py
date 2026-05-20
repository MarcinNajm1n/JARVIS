from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime
from typing import Any

from src.config import Settings, load_settings
from src.json_store import read_json, write_json


@dataclass(frozen=True)
class UsageRecord:
    model: str
    input_tokens: int
    output_tokens: int
    estimated_cost_usd: float
    source: str


class CostTracker:
    def __init__(self, settings: Settings | None = None) -> None:
        self.settings = settings or load_settings()
        self._data = read_json(self.settings.cost_log_path, self._default())

    def record_llm_usage(
        self,
        model: str,
        input_tokens: int,
        output_tokens: int,
        source: str,
    ) -> UsageRecord:
        input_tokens = max(0, int(input_tokens))
        output_tokens = max(0, int(output_tokens))
        cost = self.estimate_cost_usd(model, input_tokens, output_tokens)
        record = {
            "created_at": datetime.now().isoformat(timespec="seconds"),
            "model": model,
            "input_tokens": input_tokens,
            "output_tokens": output_tokens,
            "estimated_cost_usd": cost,
            "source": source,
        }
        self._data.setdefault("records", []).append(record)
        totals = self._data.setdefault("totals", {})
        totals["input_tokens"] = int(totals.get("input_tokens", 0)) + input_tokens
        totals["output_tokens"] = int(totals.get("output_tokens", 0)) + output_tokens
        totals["estimated_cost_usd"] = round(
            float(totals.get("estimated_cost_usd", 0.0)) + cost,
            8,
        )
        self.save()
        return UsageRecord(
            model=model,
            input_tokens=input_tokens,
            output_tokens=output_tokens,
            estimated_cost_usd=cost,
            source=source,
        )

    def estimate_cost_usd(self, model: str, input_tokens: int, output_tokens: int) -> float:
        if model.startswith("gpt-4.1-mini"):
            input_rate = self.settings.gpt_4_1_mini_input_cost_per_1m
            output_rate = self.settings.gpt_4_1_mini_output_cost_per_1m
        else:
            input_rate = self.settings.gpt_4_1_mini_input_cost_per_1m
            output_rate = self.settings.gpt_4_1_mini_output_cost_per_1m
        return round(
            (input_tokens / 1_000_000 * input_rate)
            + (output_tokens / 1_000_000 * output_rate),
            8,
        )

    def snapshot(self) -> dict[str, Any]:
        totals = self._data.get("totals", {})
        return {
            "model": self.settings.llm_model,
            "input_tokens": int(totals.get("input_tokens", 0)),
            "output_tokens": int(totals.get("output_tokens", 0)),
            "estimated_cost_usd": float(totals.get("estimated_cost_usd", 0.0)),
            "records_count": len(self._data.get("records", [])),
        }

    def save(self) -> None:
        write_json(self.settings.cost_log_path, self._data)

    @staticmethod
    def _default() -> dict[str, Any]:
        return {
            "totals": {
                "input_tokens": 0,
                "output_tokens": 0,
                "estimated_cost_usd": 0.0,
            },
            "records": [],
        }


def extract_response_usage(response: Any) -> tuple[int, int]:
    usage = getattr(response, "usage", None)
    if usage is None and isinstance(response, dict):
        usage = response.get("usage")
    if usage is None:
        return 0, 0

    def get_value(*names: str) -> int:
        for name in names:
            if isinstance(usage, dict) and name in usage:
                return int(usage.get(name) or 0)
            value = getattr(usage, name, None)
            if value is not None:
                return int(value or 0)
        return 0

    input_tokens = get_value("input_tokens", "prompt_tokens")
    output_tokens = get_value("output_tokens", "completion_tokens")
    return input_tokens, output_tokens
