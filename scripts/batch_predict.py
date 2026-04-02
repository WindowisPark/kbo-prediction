"""
배치 예측 — 경기 시간 기준 동적 스케줄링.

매시간 cron으로 실행 → 경기 시작 시간 기준으로 자동 판단:
  - 경기 4시간 전: Phase 1 (선발투수 기반 분석)
  - 경기 1시간 전: Phase 2 (라인업 반영 재분석)
  - 해당 없으면 스킵

사용법:
  python scripts/batch_predict.py               # 자동 (cron용)
  python scripts/batch_predict.py --phase 1     # 강제 1차 분석 (전 경기)
  python scripts/batch_predict.py --phase 2     # 강제 2차 분석 (전 경기)
  python scripts/batch_predict.py --date 20260402 --phase 1  # 특정 날짜 강제

GitHub Actions cron: '0 * * * *' (매시간 UTC) → KST 기준 자동 판단
"""
import sys
import json
import logging
import argparse
from pathlib import Path
from datetime import datetime, timezone, timedelta

ROOT = Path(__file__).parent.parent
sys.path.insert(0, str(ROOT))

from dotenv import load_dotenv
load_dotenv(ROOT / ".env", override=True)

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(message)s",
    handlers=[
        logging.StreamHandler(sys.stdout),
        logging.FileHandler(ROOT / "data" / "batch.log", encoding="utf-8"),
    ],
)
logger = logging.getLogger(__name__)

from backend.scrapers.kbo_today import get_today_games, get_game_list
from backend.scrapers.kbo_pregame_lineup import (
    get_pregame_lineup, format_lineup_context,
    get_expected_lineup, format_expected_lineup_context,
)
from backend.utils.team_mapping import unify_team
from backend.agents.predictor import GamePredictor
from backend.auth.database import init_db, SessionLocal
from backend.auth.models import PreComputedPrediction

KST = timezone(timedelta(hours=9))

# 배치 타이밍 (분 단위)
PHASE1_BEFORE_MINUTES = 240   # 경기 4시간 전
PHASE2_BEFORE_MINUTES = 60    # 경기 1시간 전
WINDOW_MINUTES = 30           # ±30분 허용 범위


def parse_game_time(game: dict) -> datetime | None:
    """경기 시간을 datetime으로 변환. time='1830', date='2026-04-02'."""
    time_str = game.get("time", "")
    date_str = game.get("date", "")

    if not time_str or len(time_str) < 4 or not date_str:
        return None

    try:
        # time: "1830" or "18:30"
        t = time_str.replace(":", "")
        hour, minute = int(t[:2]), int(t[2:4])
        # date: "2026-04-02" or "20260402"
        d = date_str.replace("-", "")
        year, month, day = int(d[:4]), int(d[4:6]), int(d[6:8])
        return datetime(year, month, day, hour, minute, tzinfo=KST)
    except (ValueError, IndexError):
        return None


def get_games_needing_batch(games: list[dict], now: datetime) -> dict[int, list[dict]]:
    """현재 시간 기준, 배치가 필요한 경기를 phase별로 분류."""
    result = {1: [], 2: []}

    for game in games:
        if game["status"] in ("final", "cancelled"):
            continue

        game_time = parse_game_time(game)
        if game_time is None:
            continue

        minutes_until = (game_time - now).total_seconds() / 60

        # Phase 1: 경기 4시간 전 ± 30분
        if (PHASE1_BEFORE_MINUTES - WINDOW_MINUTES) <= minutes_until <= (PHASE1_BEFORE_MINUTES + WINDOW_MINUTES):
            result[1].append(game)

        # Phase 2: 경기 1시간 전 ± 30분
        if (PHASE2_BEFORE_MINUTES - WINDOW_MINUTES) <= minutes_until <= (PHASE2_BEFORE_MINUTES + WINDOW_MINUTES):
            result[2].append(game)

    return result


def run_prediction(predictor: GamePredictor, game: dict, phase: int, db) -> bool:
    """단일 경기 예측 실행. 성공 시 True."""
    home = unify_team(game["home_team"])
    away = unify_team(game["away_team"])
    game_date = game["date"].replace("-", "")

    # 이미 같은 phase 결과가 있으면 스킵
    existing = db.query(PreComputedPrediction).filter(
        PreComputedPrediction.game_date == game_date,
        PreComputedPrediction.home_team == home,
        PreComputedPrediction.away_team == away,
        PreComputedPrediction.batch_phase == phase,
    ).first()

    if existing:
        logger.info(f"  Skip {away} @ {home} (phase {phase} already exists)")
        return False

    # 컨텍스트 구성
    extra_context = ""
    stadium = game.get("stadium", "")
    if stadium:
        extra_context += f"\n- 구장: {stadium}"

    home_sp = game.get("home_starter", "")
    away_sp = game.get("away_starter", "")

    if phase == 1:
        # 예상 라인업 (최근 경기 패턴 기반)
        for team_raw, team_unified in [(game["home_team"], home), (game["away_team"], away)]:
            expected = get_expected_lineup(team_raw, num_games=5)
            if expected and expected.get("lineup"):
                extra_context += format_expected_lineup_context(team_unified, expected)
                logger.info(f"    Expected lineup for {team_unified}: {expected['games_used']} games used")

    elif phase == 2:
        # 확정 라인업 수집
        game_id = game.get("game_id", "")
        if game_id:
            lineup = get_pregame_lineup(game_id)
            if lineup and lineup.get("available"):
                lineup_ctx = format_lineup_context(lineup)
                extra_context += lineup_ctx
                logger.info(f"    Lineup loaded: {len(lineup.get('home_lineup', []))} + {len(lineup.get('away_lineup', []))} players")
            else:
                extra_context += "\n- 분석 시점: 라인업 미공개 (선발투수 기반)"
                logger.info(f"    Lineup not yet available")

    logger.info(f"  Predicting: {away} @ {home} [{game.get('time', '?')}] (phase {phase})")

    try:
        result = predictor.predict_game(
            home_team=home,
            away_team=away,
            date=game_date,
            extra_context=extra_context,
            home_starter=home_sp,
            away_starter=away_sp,
            home_team_raw=game["home_team"],
            away_team_raw=game["away_team"],
        )

        prediction = PreComputedPrediction(
            game_date=game_date,
            home_team=home,
            away_team=away,
            batch_phase=phase,
            predicted_winner=result.predicted_winner,
            home_win_probability=result.home_win_probability,
            confidence=result.confidence,
            key_factors=json.dumps(result.key_factors, ensure_ascii=False),
            reasoning=result.reasoning,
            model_probabilities=json.dumps(result.model_probabilities, ensure_ascii=False),
            debate_log=json.dumps(result.debate_log, ensure_ascii=False),
        )
        db.add(prediction)
        db.commit()

        logger.info(f"    → {result.predicted_winner} ({result.home_win_probability:.1%}), "
                     f"confidence={result.confidence}")
        return True

    except Exception as e:
        logger.error(f"    → Failed: {e}")
        return False


def run_auto(target_date: str | None = None):
    """자동 모드 — 현재 시간 기준으로 배치 대상 판단."""
    now = datetime.now(KST)
    logger.info(f"{'='*60}")
    logger.info(f"Batch Predict — Auto mode")
    logger.info(f"Current time (KST): {now.strftime('%Y-%m-%d %H:%M')}")
    logger.info(f"{'='*60}")

    # 경기 목록
    if target_date:
        games = get_game_list(target_date)
    else:
        games = get_today_games()

    if not games:
        logger.info("No games found — skipping")
        return

    logger.info(f"Found {len(games)} games today")
    for g in games:
        gt = parse_game_time(g)
        gt_str = gt.strftime("%H:%M") if gt else "?"
        logger.info(f"  {g.get('time', '?'):>6s} | {g['away_team']:>4s} @ {g['home_team']:<4s} | {g['status']}")

    # 배치 대상 판단
    batch_games = get_games_needing_batch(games, now)

    phase1_games = batch_games[1]
    phase2_games = batch_games[2]

    # 누락 보충: 경기 시작 전인데 아직 배치 결과가 없는 경기
    upcoming = [g for g in games if g["status"] not in ("final", "cancelled")]
    missing_phase1 = []
    missing_phase2 = []

    if upcoming:
        init_db()
        db = SessionLocal()
        try:
            for game in upcoming:
                home = unify_team(game["home_team"])
                away = unify_team(game["away_team"])
                game_date = game["date"].replace("-", "")
                game_time = parse_game_time(game)

                if game_time and game_time > now:
                    # Phase 1 누락 체크 — 경기 시작 전이면 보충
                    p1 = db.query(PreComputedPrediction).filter(
                        PreComputedPrediction.game_date == game_date,
                        PreComputedPrediction.home_team == home,
                        PreComputedPrediction.away_team == away,
                        PreComputedPrediction.batch_phase == 1,
                    ).first()
                    if not p1:
                        missing_phase1.append(game)

                    # Phase 2 누락 체크 — 경기 2시간 전 이내이면 보충
                    minutes_until = (game_time - now).total_seconds() / 60
                    if minutes_until <= 120:
                        p2 = db.query(PreComputedPrediction).filter(
                            PreComputedPrediction.game_date == game_date,
                            PreComputedPrediction.home_team == home,
                            PreComputedPrediction.away_team == away,
                            PreComputedPrediction.batch_phase == 2,
                        ).first()
                        if not p2:
                            missing_phase2.append(game)
        finally:
            db.close()

    # 윈도우 + 누락 합산 (중복 제거)
    seen_ids = set()
    all_phase1 = []
    for g in phase1_games + missing_phase1:
        gid = g.get("game_id", "")
        if gid not in seen_ids:
            seen_ids.add(gid)
            all_phase1.append(g)

    seen_ids = set()
    all_phase2 = []
    for g in phase2_games + missing_phase2:
        gid = g.get("game_id", "")
        if gid not in seen_ids:
            seen_ids.add(gid)
            all_phase2.append(g)

    if not all_phase1 and not all_phase2:
        logger.info("No games in batch window and no missing predictions — skipping")
        return

    # 모델 로드
    init_db()
    logger.info("Loading models...")
    predictor = GamePredictor(debate_rounds=2)
    predictor.load_models()
    logger.info("Models loaded")

    db = SessionLocal()
    try:
        if all_phase1:
            n_window = len(phase1_games)
            n_missing = len(all_phase1) - n_window
            label = f"Phase 1: 선발투수 기반 ({n_window} window + {n_missing} fallback)"
            logger.info(f"\n--- {label} ---")
            for game in all_phase1:
                run_prediction(predictor, game, phase=1, db=db)

        if all_phase2:
            n_window = len(phase2_games)
            n_missing = len(all_phase2) - n_window
            label = f"Phase 2: 라인업 반영 ({n_window} window + {n_missing} fallback)"
            logger.info(f"\n--- {label} ---")
            for game in all_phase2:
                run_prediction(predictor, game, phase=2, db=db)
    finally:
        db.close()

    logger.info(f"{'='*60}")
    logger.info("Batch Predict Complete")
    logger.info(f"{'='*60}")


def run_forced(phase: int, target_date: str | None = None):
    """강제 모드 — 지정 phase로 전 경기 분석."""
    logger.info(f"{'='*60}")
    logger.info(f"Batch Predict — Forced Phase {phase}")
    logger.info(f"{'='*60}")

    init_db()

    logger.info("Loading models...")
    predictor = GamePredictor(debate_rounds=2)
    predictor.load_models()
    logger.info("Models loaded")

    if target_date:
        games = get_game_list(target_date)
    else:
        games = get_today_games()

    if not games:
        logger.info("No games found")
        return

    upcoming = [g for g in games if g["status"] not in ("final", "cancelled")]
    logger.info(f"Found {len(upcoming)} upcoming games")

    db = SessionLocal()
    try:
        count = 0
        for game in upcoming:
            if run_prediction(predictor, game, phase=phase, db=db):
                count += 1
        logger.info(f"Completed: {count}/{len(upcoming)} games")
    finally:
        db.close()

    logger.info(f"{'='*60}")
    logger.info(f"Batch Predict Phase {phase} Complete")
    logger.info(f"{'='*60}")


def main():
    parser = argparse.ArgumentParser(description="KBO Batch Predict")
    parser.add_argument("--phase", type=int, choices=[1, 2],
                        help="강제 실행: 1=선발투수, 2=라인업. 미지정 시 자동 판단")
    parser.add_argument("--date", help="Target date (YYYYMMDD), default=today")
    args = parser.parse_args()

    if args.phase:
        run_forced(phase=args.phase, target_date=args.date)
    else:
        run_auto(target_date=args.date)


if __name__ == "__main__":
    main()
