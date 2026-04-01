"""LLM API 비용 추적 모듈."""
import json
import logging
from datetime import datetime
from pathlib import Path

logger = logging.getLogger(__name__)
ROOT = Path(__file__).parent.parent.parent
COST_FILE = ROOT / "data" / "llm_costs.jsonl"

# 모델별 가격 ($ per 1M tokens)
PRICING = {
    "gemini-2.5-pro": {"input": 1.25, "output": 10.0},
    "gemini-2.5-flash": {"input": 0.15, "output": 0.6},
    "gpt-4o": {"input": 2.5, "output": 10.0},
    "gpt-4-turbo": {"input": 10.0, "output": 30.0},
    "gpt-4o-mini": {"input": 0.15, "output": 0.6},
    "claude-sonnet-4-20250514": {"input": 3.0, "output": 15.0},
    "claude-3-haiku-20240307": {"input": 0.25, "output": 1.25},
}


def log_cost(model: str, input_tokens: int, output_tokens: int, agent: str = ""):
    """API 호출 비용을 기록."""
    pricing = PRICING.get(model, {"input": 5.0, "output": 15.0})
    cost = (input_tokens * pricing["input"] + output_tokens * pricing["output"]) / 1_000_000

    entry = {
        "timestamp": datetime.now().isoformat(),
        "model": model,
        "agent": agent,
        "input_tokens": input_tokens,
        "output_tokens": output_tokens,
        "cost_usd": round(cost, 6),
    }

    try:
        with open(COST_FILE, "a", encoding="utf-8") as f:
            f.write(json.dumps(entry) + "\n")
    except Exception as e:
        logger.warning(f"Cost logging failed: {e}")

    return cost


def get_daily_summary(date_str: str = "") -> dict:
    """일일 비용 요약."""
    if not date_str:
        date_str = datetime.now().strftime("%Y-%m-%d")

    if not COST_FILE.exists():
        return {"date": date_str, "total_cost": 0, "total_calls": 0, "by_model": {}}

    total_cost = 0
    total_calls = 0
    by_model: dict[str, dict] = {}

    with open(COST_FILE, "r", encoding="utf-8") as f:
        for line in f:
            try:
                entry = json.loads(line)
                if entry["timestamp"].startswith(date_str):
                    total_cost += entry["cost_usd"]
                    total_calls += 1
                    m = entry["model"]
                    if m not in by_model:
                        by_model[m] = {"calls": 0, "cost": 0, "tokens": 0}
                    by_model[m]["calls"] += 1
                    by_model[m]["cost"] += entry["cost_usd"]
                    by_model[m]["tokens"] += entry["input_tokens"] + entry["output_tokens"]
            except (json.JSONDecodeError, KeyError):
                continue

    return {
        "date": date_str,
        "total_cost": round(total_cost, 4),
        "total_calls": total_calls,
        "by_model": {k: {**v, "cost": round(v["cost"], 4)} for k, v in by_model.items()},
    }


def get_monthly_summary() -> dict:
    """월간 비용 요약."""
    month_str = datetime.now().strftime("%Y-%m")

    if not COST_FILE.exists():
        return {"month": month_str, "total_cost": 0, "total_calls": 0}

    total_cost = 0
    total_calls = 0

    with open(COST_FILE, "r", encoding="utf-8") as f:
        for line in f:
            try:
                entry = json.loads(line)
                if entry["timestamp"][:7] == month_str:
                    total_cost += entry["cost_usd"]
                    total_calls += 1
            except (json.JSONDecodeError, KeyError):
                continue

    return {"month": month_str, "total_cost": round(total_cost, 4), "total_calls": total_calls}
