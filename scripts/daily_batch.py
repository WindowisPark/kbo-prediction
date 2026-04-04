"""
일일 배치 — 매일 자정 실행.

1. 어제 경기 결과 수집
2. 예측 적중 여부 업데이트
3. ELO 레이팅 갱신
4. 피처 매트릭스 업데이트
5. 오늘 경기 자동 예측 (선택)

사용법:
  python scripts/daily_batch.py              # 전체 실행
  python scripts/daily_batch.py --no-predict # 예측 없이 데이터만 갱신
  python scripts/daily_batch.py --date 20260330  # 특정 날짜 결과 처리
"""
import sys
import json
import logging
import argparse
from pathlib import Path
from datetime import datetime, timedelta

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

from backend.scrapers.kbo_today import get_game_list, get_next_game_date
from backend.utils.team_mapping import unify_team


def step1_collect_results(target_date: str) -> list[dict]:
    """어제(또는 지정 날짜) 경기 결과 수집."""
    logger.info(f"Step 1: Collecting results for {target_date}")
    games = get_game_list(target_date)
    completed = [g for g in games if g["status"] == "final"]
    logger.info(f"  Found {len(completed)} completed games")

    # raw 결과 저장 (append)
    results_file = ROOT / "data" / "daily_results.jsonl"
    with open(results_file, "a", encoding="utf-8") as f:
        for g in completed:
            g["collected_at"] = datetime.now().isoformat()
            f.write(json.dumps(g, ensure_ascii=False) + "\n")

    return completed


def step2_update_predictions(completed: list[dict]):
    """예측 적중 여부 업데이트."""
    logger.info("Step 2: Updating prediction accuracy")
    history_file = ROOT / "data" / "prediction_history.json"
    if not history_file.exists():
        logger.info("  No prediction history found")
        return

    history = json.loads(history_file.read_text(encoding="utf-8"))
    updated = 0

    # 경기별 최신 예측만 사용 (중복 제거 — 같은 경기 여러 번 예측 시 마지막만)
    seen_games = set()
    unique_preds = []
    for pred in reversed(history):
        game_key = f"{pred['date']}_{pred['home_team']}_{pred['away_team']}"
        if game_key not in seen_games:
            seen_games.add(game_key)
            unique_preds.append(pred)
    unique_preds.reverse()

    for pred in unique_preds:
        if pred.get("actual_winner"):
            continue

        for game in completed:
            home = unify_team(game["home_team"])
            away = unify_team(game["away_team"])
            if pred["home_team"] == home and pred["away_team"] == away and pred["date"] == game["date"]:
                # 무승부 처리
                if game["home_score"] == game["away_score"]:
                    pred["actual_winner"] = "draw"
                    pred["is_draw"] = True
                    logger.info(f"  {away} @ {home}: 무승부 ({game['away_score']}-{game['home_score']}) — 적중률 제외")
                else:
                    if game["home_score"] > game["away_score"]:
                        pred["actual_winner"] = home
                    else:
                        pred["actual_winner"] = away
                    pred["is_draw"] = False
                    is_correct = pred["predicted_winner"] == pred["actual_winner"]
                    logger.info(f"  {away} @ {home}: predicted={pred['predicted_winner']}, "
                               f"actual={pred['actual_winner']} {'O' if is_correct else 'X'}")

                pred["home_score"] = game["home_score"]
                pred["away_score"] = game["away_score"]
                updated += 1

    # 중복 제거된 결과를 history에 반영
    # (원본 history의 해당 항목을 업데이트)
    pred_map = {f"{p['date']}_{p['home_team']}_{p['away_team']}": p for p in unique_preds if p.get("actual_winner")}
    for pred in history:
        key = f"{pred['date']}_{pred['home_team']}_{pred['away_team']}"
        if key in pred_map:
            pred["actual_winner"] = pred_map[key]["actual_winner"]
            pred["is_draw"] = pred_map[key].get("is_draw", False)
            if "home_score" in pred_map[key]:
                pred["home_score"] = pred_map[key]["home_score"]
                pred["away_score"] = pred_map[key]["away_score"]

    history_file.write_text(json.dumps(history, ensure_ascii=False, indent=2), encoding="utf-8")
    logger.info(f"  Updated {updated} predictions")

    # 적중률 계산 (무승부 제외, 경기별 최신 예측만)
    verified = [p for p in unique_preds if p.get("actual_winner") and not p.get("is_draw")]
    draws = sum(1 for p in unique_preds if p.get("is_draw"))
    if verified:
        correct = sum(1 for p in verified if p["predicted_winner"] == p["actual_winner"])
        logger.info(f"  Overall accuracy: {correct}/{len(verified)} ({correct/len(verified)*100:.1f}%) — draws excluded: {draws}")


def step3_update_elo(completed: list[dict]):
    """ELO 레이팅 갱신 — 새 경기 결과 반영."""
    logger.info("Step 3: Updating ELO ratings")
    elo_file = ROOT / "data" / "elo_ratings.json"

    # 기존 ELO 로드
    if elo_file.exists():
        elo = json.loads(elo_file.read_text(encoding="utf-8"))
    else:
        elo = {}

    import numpy as np
    k = 20
    home_adv = 20

    for game in completed:
        home = unify_team(game["home_team"])
        away = unify_team(game["away_team"])

        if home not in elo:
            elo[home] = 1500.0
        if away not in elo:
            elo[away] = 1500.0

        home_elo = elo[home]
        away_elo = elo[away]

        expected = 1 / (1 + 10 ** ((away_elo - home_elo - home_adv) / 400))
        actual = 1 if game["home_score"] > game["away_score"] else 0
        margin = abs(game["home_score"] - game["away_score"])
        elo_diff_winner = (home_elo - away_elo) if actual == 1 else (away_elo - home_elo)
        margin_mult = np.log(margin + 1) * (2.2 / (elo_diff_winner * 0.001 + 2.2))

        update = k * margin_mult * (actual - expected)
        elo[home] = home_elo + update
        elo[away] = away_elo - update

        result = "W" if actual == 1 else "L"
        logger.info(f"  {away} @ {home}: {game['away_score']}-{game['home_score']} "
                    f"| {home} ELO {home_elo:.0f} -> {elo[home]:.0f} "
                    f"| {away} ELO {away_elo:.0f} -> {elo[away]:.0f}")

    # 저장
    elo_file.write_text(json.dumps(elo, ensure_ascii=False, indent=2), encoding="utf-8")
    logger.info(f"  ELO ratings saved ({len(elo)} teams)")

    # 순위 출력
    sorted_elo = sorted(elo.items(), key=lambda x: x[1], reverse=True)
    logger.info("  Current rankings:")
    for i, (team, rating) in enumerate(sorted_elo, 1):
        logger.info(f"    {i}. {team:10s} {rating:.0f}")


def step4_update_standings(completed: list[dict]):
    """시즌 순위표 + 연승/연패 갱신 → data/standings.json 저장."""
    logger.info("Step 4: Updating standings")
    results_file = ROOT / "data" / "daily_results.jsonl"
    if not results_file.exists():
        logger.warning("  daily_results.jsonl not found, skipping")
        return

    current_season = str(datetime.now().year)
    games = []
    for line in results_file.read_text(encoding="utf-8").strip().split("\n"):
        if line:
            g = json.loads(line)
            if g["date"].startswith(current_season):
                games.append(g)

    games.sort(key=lambda g: g["date"])

    team_stats: dict[str, dict] = {}
    for g in games:
        home = unify_team(g["home_team"])
        away = unify_team(g["away_team"])
        hs, as_ = g["home_score"], g["away_score"]

        for t in [home, away]:
            if t not in team_stats:
                team_stats[t] = {"wins": 0, "losses": 0, "draws": 0, "results": []}

        if hs > as_:
            team_stats[home]["wins"] += 1
            team_stats[home]["results"].append("W")
            team_stats[away]["losses"] += 1
            team_stats[away]["results"].append("L")
        elif hs < as_:
            team_stats[away]["wins"] += 1
            team_stats[away]["results"].append("W")
            team_stats[home]["losses"] += 1
            team_stats[home]["results"].append("L")
        else:
            team_stats[home]["draws"] += 1
            team_stats[home]["results"].append("D")
            team_stats[away]["draws"] += 1
            team_stats[away]["results"].append("D")

    standings = {}
    for team, s in team_stats.items():
        total = s["wins"] + s["losses"]
        win_pct = round(s["wins"] / total, 3) if total > 0 else 0.5

        # 연승/연패 계산
        streak = 0
        for r in reversed(s["results"]):
            if r == "D":
                continue
            if streak == 0:
                streak = 1 if r == "W" else -1
            elif (streak > 0 and r == "W") or (streak < 0 and r == "L"):
                streak += 1 if streak > 0 else -1
            else:
                break

        standings[team] = {
            "wins": s["wins"],
            "losses": s["losses"],
            "draws": s["draws"],
            "games_played": s["wins"] + s["losses"] + s["draws"],
            "win_pct": win_pct,
            "streak": streak,
        }
        logger.info(f"  {team:6s} {s['wins']}W-{s['losses']}L-{s['draws']}D "
                    f"({win_pct:.3f}) streak={streak:+d}")

    standings_file = ROOT / "data" / "standings.json"
    output = {
        "season": int(current_season),
        "updated_at": datetime.now().isoformat(),
        "teams": standings,
    }
    standings_file.write_text(json.dumps(output, ensure_ascii=False, indent=2), encoding="utf-8")
    logger.info(f"  Standings saved ({len(standings)} teams)")


def step5_append_games(completed: list[dict]):
    """경기 결과를 메인 CSV에 추가."""
    logger.info("Step 5: Appending games to dataset")
    import pandas as pd

    games_file = ROOT / "data" / "raw" / "kbo_games_2000_2025.csv"
    if not games_file.exists():
        logger.warning("  games CSV not found, skipping append")
        return
    df = pd.read_csv(games_file)
    existing_ids = set(df["game_id"].values)

    new_rows = []
    for g in completed:
        if g["game_id"] not in existing_ids:
            new_rows.append({
                "game_id": g["game_id"],
                "date": g["date"],
                "away_team": g["away_team"],
                "home_team": g["home_team"],
                "away_score": g["away_score"],
                "home_score": g["home_score"],
                "stadium": g.get("stadium", ""),
                "season": int(g["date"][:4]),
            })

    if new_rows:
        new_df = pd.DataFrame(new_rows)
        combined = pd.concat([df, new_df], ignore_index=True)
        combined.to_csv(games_file, index=False, encoding="utf-8-sig")
        logger.info(f"  Added {len(new_rows)} new games (total: {len(combined)})")
    else:
        logger.info("  No new games to add")


def step6_summary():
    """일일 요약 리포트."""
    logger.info("Step 6: Daily summary")
    history_file = ROOT / "data" / "prediction_history.json"
    if not history_file.exists():
        return

    history = json.loads(history_file.read_text(encoding="utf-8"))
    total = len(history)
    verified = [p for p in history if p.get("actual_winner")]
    correct = sum(1 for p in verified if p["predicted_winner"] == p["actual_winner"])

    logger.info(f"  Total predictions: {total}")
    logger.info(f"  Verified: {len(verified)}")
    if verified:
        logger.info(f"  Correct: {correct} ({correct/len(verified)*100:.1f}%)")

        # confidence별
        for conf in ["low", "medium", "high"]:
            subset = [p for p in verified if p.get("confidence") == conf]
            if subset:
                c = sum(1 for p in subset if p["predicted_winner"] == p["actual_winner"])
                logger.info(f"    {conf}: {c}/{len(subset)} ({c/len(subset)*100:.1f}%)")


def main():
    parser = argparse.ArgumentParser(description="KBO Daily Batch")
    parser.add_argument("--date", help="Process specific date (YYYYMMDD)")
    parser.add_argument("--no-predict", action="store_true", help="Skip auto-prediction")
    args = parser.parse_args()

    logger.info("=" * 60)
    logger.info("KBO Daily Batch Start")
    logger.info("=" * 60)

    # 대상 날짜 결정
    if args.date:
        target = args.date
    else:
        # 어제 날짜
        yesterday = datetime.now() - timedelta(days=1)
        target = yesterday.strftime("%Y%m%d")

    logger.info(f"Target date: {target}")

    # Step 1: 결과 수집
    completed = step1_collect_results(target)

    if completed:
        # Step 2: 적중 여부 업데이트
        step2_update_predictions(completed)

        # Step 3: ELO 갱신
        step3_update_elo(completed)

        # Step 4: 순위표 + 연승/연패 갱신
        step4_update_standings(completed)

        # Step 5: 데이터셋 추가
        step5_append_games(completed)
    else:
        logger.info("No completed games found — skipping steps 2-5")

    # Step 6: 요약
    step6_summary()

    logger.info("=" * 60)
    logger.info("KBO Daily Batch Complete")
    logger.info("=" * 60)


if __name__ == "__main__":
    main()
