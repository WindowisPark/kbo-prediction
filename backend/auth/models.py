"""ORM 모델 — User + PreComputedPrediction."""
from datetime import datetime

from sqlalchemy import String, Boolean, DateTime, Float, Text, Integer, func
from sqlalchemy.orm import Mapped, mapped_column

from backend.auth.database import Base


class User(Base):
    __tablename__ = "users"

    id: Mapped[int] = mapped_column(primary_key=True, autoincrement=True)
    email: Mapped[str] = mapped_column(String(255), unique=True, nullable=False, index=True)
    nickname: Mapped[str] = mapped_column(String(100), nullable=False)
    password_hash: Mapped[str] = mapped_column(String(255), nullable=False)
    tier: Mapped[str] = mapped_column(String(20), default="free", nullable=False)
    is_active: Mapped[bool] = mapped_column(Boolean, default=True)
    is_verified: Mapped[bool] = mapped_column(Boolean, default=False)
    stripe_customer_id: Mapped[str | None] = mapped_column(String(255), nullable=True)
    stripe_subscription_id: Mapped[str | None] = mapped_column(String(255), nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=func.now())
    updated_at: Mapped[datetime] = mapped_column(DateTime, default=func.now(), onupdate=func.now())


class VerificationCode(Base):
    """이메일 인증 코드."""
    __tablename__ = "verification_codes"

    id: Mapped[int] = mapped_column(primary_key=True, autoincrement=True)
    email: Mapped[str] = mapped_column(String(255), nullable=False, index=True)
    code: Mapped[str] = mapped_column(String(6), nullable=False)
    expires_at: Mapped[datetime] = mapped_column(DateTime, nullable=False)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=func.now())


class PredictionHistory(Base):
    """분석 이력 — 영구 보존."""
    __tablename__ = "prediction_history"

    id: Mapped[int] = mapped_column(primary_key=True, autoincrement=True)
    date: Mapped[str] = mapped_column(String(20), nullable=False, index=True)
    home_team: Mapped[str] = mapped_column(String(50), nullable=False)
    away_team: Mapped[str] = mapped_column(String(50), nullable=False)
    predicted_winner: Mapped[str] = mapped_column(String(50), nullable=False)
    home_win_probability: Mapped[float] = mapped_column(Float, nullable=False)
    confidence: Mapped[str] = mapped_column(String(20), nullable=False)
    key_factors: Mapped[str] = mapped_column(Text, nullable=False)  # JSON array
    model_probs: Mapped[str] = mapped_column(Text, nullable=False)  # JSON
    actual_winner: Mapped[str | None] = mapped_column(String(50), nullable=True)
    is_draw: Mapped[bool] = mapped_column(Boolean, default=False)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=func.now())


class LLMCostLog(Base):
    """LLM API 비용 로그 — 영구 보존."""
    __tablename__ = "llm_cost_logs"

    id: Mapped[int] = mapped_column(primary_key=True, autoincrement=True)
    model: Mapped[str] = mapped_column(String(100), nullable=False)
    agent: Mapped[str] = mapped_column(String(100), nullable=False, default="")
    input_tokens: Mapped[int] = mapped_column(Integer, nullable=False)
    output_tokens: Mapped[int] = mapped_column(Integer, nullable=False)
    cost_usd: Mapped[float] = mapped_column(Float, nullable=False)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=func.now(), index=True)


class PreComputedPrediction(Base):
    """배치 사전 분석 결과 — 1차(선발투수), 2차(실제 라인업)."""
    __tablename__ = "pre_computed_predictions"

    id: Mapped[int] = mapped_column(primary_key=True, autoincrement=True)
    game_date: Mapped[str] = mapped_column(String(10), nullable=False, index=True)  # YYYYMMDD
    home_team: Mapped[str] = mapped_column(String(50), nullable=False)
    away_team: Mapped[str] = mapped_column(String(50), nullable=False)
    batch_phase: Mapped[int] = mapped_column(Integer, nullable=False)  # 1=선발투수, 2=실제라인업
    predicted_winner: Mapped[str] = mapped_column(String(50), nullable=False)
    home_win_probability: Mapped[float] = mapped_column(Float, nullable=False)
    confidence: Mapped[str] = mapped_column(String(20), nullable=False)
    key_factors: Mapped[str] = mapped_column(Text, nullable=False)  # JSON array
    reasoning: Mapped[str] = mapped_column(Text, nullable=False)
    model_probabilities: Mapped[str] = mapped_column(Text, nullable=False)  # JSON
    debate_log: Mapped[str] = mapped_column(Text, nullable=False)  # JSON array
    created_at: Mapped[datetime] = mapped_column(DateTime, default=func.now())
