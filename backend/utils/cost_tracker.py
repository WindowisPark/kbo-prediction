"""LLM API 비용 추적 모듈 — PostgreSQL 저장."""
import logging
from datetime import datetime

logger = logging.getLogger(__name__)

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
    """API 호출 비용을 DB에 기록."""
    pricing = PRICING.get(model, {"input": 5.0, "output": 15.0})
    cost = (input_tokens * pricing["input"] + output_tokens * pricing["output"]) / 1_000_000

    try:
        from backend.auth.database import SessionLocal
        from backend.auth.models import LLMCostLog

        db = SessionLocal()
        try:
            row = LLMCostLog(
                model=model, agent=agent,
                input_tokens=input_tokens, output_tokens=output_tokens,
                cost_usd=round(cost, 6),
            )
            db.add(row)
            db.commit()
        finally:
            db.close()
    except Exception as e:
        logger.warning(f"Cost logging failed: {e}")

    return cost


def get_daily_summary(date_str: str = "") -> dict:
    """일일 비용 요약."""
    if not date_str:
        date_str = datetime.now().strftime("%Y-%m-%d")

    try:
        from backend.auth.database import SessionLocal
        from backend.auth.models import LLMCostLog

        db = SessionLocal()
        try:
            rows = db.query(LLMCostLog).all()
            rows = [r for r in rows if r.created_at and r.created_at.strftime("%Y-%m-%d") == date_str]

            total_cost = sum(r.cost_usd for r in rows)
            total_calls = len(rows)
            by_model: dict[str, dict] = {}
            for r in rows:
                if r.model not in by_model:
                    by_model[r.model] = {"calls": 0, "cost": 0, "tokens": 0}
                by_model[r.model]["calls"] += 1
                by_model[r.model]["cost"] += r.cost_usd
                by_model[r.model]["tokens"] += r.input_tokens + r.output_tokens

            return {
                "date": date_str,
                "total_cost": round(total_cost, 4),
                "total_calls": total_calls,
                "by_model": {k: {**v, "cost": round(v["cost"], 4)} for k, v in by_model.items()},
            }
        finally:
            db.close()
    except Exception as e:
        logger.warning(f"Cost summary failed: {e}")
        return {"date": date_str, "total_cost": 0, "total_calls": 0, "by_model": {}}


def get_monthly_summary() -> dict:
    """월간 비용 요약."""
    month_str = datetime.now().strftime("%Y-%m")

    try:
        from backend.auth.database import SessionLocal
        from backend.auth.models import LLMCostLog

        db = SessionLocal()
        try:
            rows = db.query(LLMCostLog).all()
            rows = [r for r in rows if r.created_at and r.created_at.strftime("%Y-%m") == month_str]

            total_cost = sum(r.cost_usd for r in rows)
            total_calls = len(rows)

            return {"month": month_str, "total_cost": round(total_cost, 4), "total_calls": total_calls}
        finally:
            db.close()
    except Exception as e:
        logger.warning(f"Monthly summary failed: {e}")
        return {"month": month_str, "total_cost": 0, "total_calls": 0}
