"""API 요청/응답 스키마."""
from pydantic import BaseModel, Field


class PredictionRequest(BaseModel):
    home_team: str
    away_team: str
    date: str  # YYYY-MM-DD
    extra_context: str = ""
    home_starter: str = ""
    away_starter: str = ""
    reanalyze: bool = False  # Pro 전용: 실시간 재분석 요청


class BatchPredictionRequest(BaseModel):
    games: list[PredictionRequest]


class ModelProbabilities(BaseModel):
    xgboost: float
    elo: float
    ensemble: float
    ai_combined: float


class DebateEntry(BaseModel):
    agent: str
    model: str
    round: int | str
    probability: float | None = None
    confidence: str | None = None
    content: str


class PredictionResponse(BaseModel):
    home_team: str
    away_team: str
    date: str = ""
    predicted_winner: str
    home_win_probability: float
    confidence: str
    key_factors: list[str]
    reasoning: str
    model_probabilities: ModelProbabilities
    debate_log: list[DebateEntry]


class TeamInfo(BaseModel):
    team: str
    elo: float
    recent_win_pct: float
    streak: int


class StandingsResponse(BaseModel):
    season: int
    teams: list[TeamInfo]


class AccuracyResponse(BaseModel):
    total_predictions: int
    correct: int
    accuracy: float
    by_confidence: dict[str, dict]
