"""
FastAPI 백엔드 — KBO 경기 예측 API.

엔드포인트:
  GET  /                    헬스체크
  POST /predict             단일 경기 예측
  POST /predict/batch       복수 경기 예측
  GET  /standings           현재 ELO 순위
  GET  /predictions         과거 예측 이력
  GET  /accuracy            적중률 통계
  GET  /teams               팀 목록
"""
import sys
import json
import logging
import asyncio
from pathlib import Path
from datetime import datetime
from contextlib import asynccontextmanager
from concurrent.futures import ThreadPoolExecutor

from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware

ROOT = Path(__file__).parent.parent.parent
sys.path.insert(0, str(ROOT))

import os
from dotenv import load_dotenv
load_dotenv(ROOT / ".env", override=True)

from backend.api.schemas import (
    PredictionRequest, BatchPredictionRequest, PredictionResponse,
    ModelProbabilities, DebateEntry, StandingsResponse, TeamInfo,
    AccuracyResponse,
)
from backend.agents.predictor import GamePredictor
from backend.scrapers.kbo_today import get_today_games, get_next_game_date, get_games_for_date
from backend.scrapers.kbo_lineup import get_lineup
from backend.utils.team_mapping import CURRENT_TEAMS, unify_team

logger = logging.getLogger(__name__)

# 글로벌 predictor
predictor: GamePredictor | None = None
prediction_history: list[dict] = []
executor = ThreadPoolExecutor(max_workers=5)  # 최대 5경기 동시 예측

HISTORY_FILE = ROOT / "data" / "prediction_history.json"


def load_history():
    global prediction_history
    if HISTORY_FILE.exists():
        prediction_history = json.loads(HISTORY_FILE.read_text(encoding="utf-8"))


def save_history():
    HISTORY_FILE.write_text(
        json.dumps(prediction_history, ensure_ascii=False, indent=2),
        encoding="utf-8"
    )


@asynccontextmanager
async def lifespan(app: FastAPI):
    """앱 시작 시 모델 로드."""
    global predictor
    logger.info("Loading models...")
    predictor = GamePredictor(debate_rounds=2)
    predictor.load_models()
    load_history()
    logger.info("Ready!")
    yield
    logger.info("Shutting down...")


app = FastAPI(
    title="KBO Prediction API",
    description="KBO 경기 예측 — ML 모델 + 멀티 에이전트 토론",
    version="1.0.0",
    lifespan=lifespan,
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


@app.get("/")
async def health():
    return {
        "status": "ok",
        "models_loaded": predictor is not None,
        "prediction_count": len(prediction_history),
    }


@app.post("/predict", response_model=PredictionResponse)
async def predict_game(req: PredictionRequest):
    """단일 경기 예측 (async — 동시 요청 가능)."""
    if predictor is None:
        raise HTTPException(500, "Models not loaded")

    loop = asyncio.get_event_loop()
    try:
        result = await loop.run_in_executor(
            executor,
            lambda: predictor.predict_game(
                home_team=req.home_team,
                away_team=req.away_team,
                date=req.date,
                extra_context=req.extra_context,
                home_starter=req.home_starter,
                away_starter=req.away_starter,
                home_team_raw=req.home_team,
                away_team_raw=req.away_team,
            ),
        )
    except Exception as e:
        logger.error(f"Prediction failed: {e}")
        raise HTTPException(500, f"Prediction failed: {str(e)}")

    response = PredictionResponse(
        home_team=result.home_team,
        away_team=result.away_team,
        date=req.date,
        predicted_winner=result.predicted_winner,
        home_win_probability=result.home_win_probability,
        confidence=result.confidence,
        key_factors=result.key_factors,
        reasoning=result.reasoning,
        model_probabilities=ModelProbabilities(**result.model_probabilities),
        debate_log=[DebateEntry(**entry) for entry in result.debate_log],
    )

    # 이력 저장
    prediction_history.append({
        "date": req.date,
        "home_team": result.home_team,
        "away_team": result.away_team,
        "predicted_winner": result.predicted_winner,
        "home_win_probability": result.home_win_probability,
        "confidence": result.confidence,
        "key_factors": result.key_factors,
        "model_probs": result.model_probabilities,
        "created_at": datetime.now().isoformat(),
        "actual_winner": None,  # 경기 후 업데이트
    })
    save_history()

    return response


@app.post("/predict/batch")
async def predict_batch(req: BatchPredictionRequest):
    """복수 경기 예측."""
    if predictor is None:
        raise HTTPException(500, "Models not loaded")

    results = []
    for game in req.games:
        try:
            result = predictor.predict_game(
                home_team=game.home_team,
                away_team=game.away_team,
                date=game.date,
                extra_context=game.extra_context,
            )
            results.append({
                "home_team": result.home_team,
                "away_team": result.away_team,
                "date": game.date,
                "predicted_winner": result.predicted_winner,
                "home_win_probability": result.home_win_probability,
                "confidence": result.confidence,
                "key_factors": result.key_factors,
                "reasoning": result.reasoning,
            })
        except Exception as e:
            results.append({
                "home_team": game.home_team,
                "away_team": game.away_team,
                "date": game.date,
                "error": str(e),
            })

    return {"predictions": results}


@app.get("/standings", response_model=StandingsResponse)
async def get_standings():
    """현재 ELO 순위."""
    if predictor is None or predictor.elo is None:
        raise HTTPException(500, "Models not loaded")

    rankings = predictor.elo.get_rankings()
    teams = []
    for _, row in rankings.iterrows():
        team = row["team"]
        ctx = predictor._get_team_context(team)
        teams.append(TeamInfo(
            team=team,
            elo=round(row["elo"], 1),
            recent_win_pct=round(ctx.get("win_pct_10", 0.5), 3),
            streak=int(ctx.get("streak", 0)),
        ))

    return StandingsResponse(season=2025, teams=teams)


@app.get("/predictions")
async def get_predictions(limit: int = 50):
    """과거 예측 이력."""
    return {"predictions": prediction_history[-limit:]}


@app.get("/accuracy", response_model=AccuracyResponse)
async def get_accuracy():
    """적중률 통계 (무승부 제외, 경기별 최신 예측만)."""
    # 경기별 중복 제거 (최신만)
    seen = set()
    unique = []
    for p in reversed(prediction_history):
        key = f"{p['date']}_{p['home_team']}_{p['away_team']}"
        if key not in seen:
            seen.add(key)
            unique.append(p)
    unique.reverse()

    # 무승부 제외
    completed = [p for p in unique if p.get("actual_winner") and not p.get("is_draw")]
    draws = sum(1 for p in unique if p.get("is_draw"))

    if not completed:
        return AccuracyResponse(
            total_predictions=len(unique),
            correct=0,
            accuracy=0.0,
            by_confidence={"draws_excluded": {"total": draws, "correct": 0, "accuracy": 0}},
        )

    correct = sum(1 for p in completed if p["predicted_winner"] == p["actual_winner"])

    by_conf: dict[str, dict] = {}
    for conf in ["low", "medium", "high"]:
        subset = [p for p in completed if p.get("confidence") == conf]
        if subset:
            c = sum(1 for p in subset if p["predicted_winner"] == p["actual_winner"])
            by_conf[conf] = {"total": len(subset), "correct": c, "accuracy": c / len(subset)}

    return AccuracyResponse(
        total_predictions=len(unique),
        correct=correct,
        accuracy=correct / len(completed),
        by_confidence=by_conf,
    )


@app.put("/predictions/{index}/result")
async def update_result(index: int, actual_winner: str):
    """경기 결과 업데이트 (적중 여부 체크용)."""
    if index >= len(prediction_history):
        raise HTTPException(404, "Prediction not found")

    prediction_history[index]["actual_winner"] = actual_winner
    save_history()
    return {"status": "updated"}


@app.get("/teams")
async def get_teams():
    """현재 KBO 팀 목록."""
    return {"teams": CURRENT_TEAMS}


@app.get("/today")
async def today_games(date: str | None = None):
    """경기 일정. date=YYYYMMDD 지정 시 해당 날짜, 미지정 시 오늘."""
    try:
        from backend.scrapers.kbo_today import get_game_list
        dates = get_next_game_date()

        if date:
            target = date
        else:
            target = dates.get("current", "")

        games = get_game_list(target) if target else []

        # 해당 날짜 기준 이전/다음 경기일 계산
        prev_date = dates.get("prev", "")
        next_date = dates.get("next", "")

        # date 파라미터가 있으면 해당 날짜 기준으로 prev/next 재계산
        if date:
            from datetime import datetime, timedelta
            dt = datetime.strptime(date, "%Y%m%d")
            prev_date = (dt - timedelta(days=1)).strftime("%Y%m%d")
            next_date = (dt + timedelta(days=1)).strftime("%Y%m%d")

        return {
            "game_date": target,
            "game_date_text": f"{target[:4]}.{target[4:6]}.{target[6:8]}" if target else "",
            "prev_date": prev_date,
            "next_date": next_date,
            "games": games,
        }
    except Exception as e:
        raise HTTPException(500, f"Schedule fetch failed: {str(e)}")


@app.post("/today/predict")
async def predict_today():
    """오늘 전 경기 일괄 예측."""
    if predictor is None:
        raise HTTPException(500, "Models not loaded")

    games = get_today_games()
    if not games:
        return {"game_date": "", "predictions": [], "message": "No games today"}

    results = []
    for game in games:
        if game["status"] == "final":
            results.append({**game, "prediction": None, "note": "already finished"})
            continue

        try:
            home = unify_team(game["home_team"])
            away = unify_team(game["away_team"])

            away_sp = game.get("away_starter", "")
            home_sp = game.get("home_starter", "")
            stadium = game.get("stadium", "")
            stadium_ctx = f"\n- 구장: {stadium}" if stadium else ""

            result = predictor.predict_game(
                home_team=home,
                away_team=away,
                date=game["date"],
                extra_context=stadium_ctx,
                home_starter=home_sp,
                away_starter=away_sp,
                home_team_raw=game["home_team"],
                away_team_raw=game["away_team"],
            )

            pred = {
                "predicted_winner": result.predicted_winner,
                "home_win_probability": result.home_win_probability,
                "confidence": result.confidence,
                "key_factors": result.key_factors,
                "reasoning": result.reasoning,
                "model_probabilities": result.model_probabilities,
                "debate_log": result.debate_log,
            }
            results.append({**game, "prediction": pred})

            # 이력 저장
            prediction_history.append({
                "date": game["date"],
                "home_team": home,
                "away_team": away,
                "predicted_winner": result.predicted_winner,
                "home_win_probability": result.home_win_probability,
                "confidence": result.confidence,
                "key_factors": result.key_factors,
                "model_probs": result.model_probabilities,
                "created_at": datetime.now().isoformat(),
                "actual_winner": None,
            })
        except Exception as e:
            results.append({**game, "prediction": None, "error": str(e)})

    save_history()

    dates = get_next_game_date()
    return {
        "game_date": dates.get("current", ""),
        "game_date_text": dates.get("current_text", ""),
        "predictions": results,
    }


@app.get("/schedule/{date}")
async def get_schedule(date: str):
    """특정 날짜 경기 일정. date: YYYYMMDD."""
    try:
        games = get_games_for_date(date)
        return {"date": date, "games": games}
    except Exception as e:
        raise HTTPException(500, str(e))


@app.get("/game/{game_id}/lineup")
async def game_lineup(game_id: str):
    """경기 라인업 조회."""
    try:
        result = get_lineup(game_id)
        if not result or (not result.get("away_lineup") and not result.get("home_lineup")):
            return {
                "game_id": game_id,
                "available": False,
                "message": "경기 종료 후 라인업이 공개됩니다 (진행 중/예정 경기는 미지원)",
            }
        return {"game_id": game_id, "available": True, **result}
    except Exception as e:
        raise HTTPException(500, str(e))
