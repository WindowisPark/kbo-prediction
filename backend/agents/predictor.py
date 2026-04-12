"""
전체 예측 파이프라인 — ML 모델 + 멀티 에이전트 토론.

사용법:
  predictor = GamePredictor()
  predictor.load_models()
  result = predictor.predict_game(home_team="KIA", away_team="LG", date="2025-04-15")
"""
import sys
import json
import logging
from pathlib import Path
from dataclasses import asdict

import pandas as pd
import numpy as np

ROOT = Path(__file__).parent.parent.parent
sys.path.insert(0, str(ROOT))

from backend.models.xgboost_model import XGBoostPredictor
from backend.models.elo_model import ELOPredictor
from backend.models.bayesian_model import BayesianPredictor
from backend.models.stacking_model import StackingPredictor
from backend.agents.debate import DebatePipeline, GameContext, DebateResult
from backend.agents.context_gatherer import gather_full_context
from backend.utils.team_mapping import unify_team
from backend.utils.player_stats import load_pitcher_data

logger = logging.getLogger(__name__)


class GamePredictor:
    """ML 모델 + 에이전트 토론을 결합한 경기 예측기."""

    def __init__(self, features_path: str | Path = None, debate_rounds: int = 2):
        self.features_path = features_path or ROOT / "data" / "features" / "game_features_v5.csv"
        self.debate_rounds = debate_rounds
        self.features_df = None
        self.pitcher_df = None
        self.batting_df = None
        self.xgb = None
        self.elo = None
        self.bay = None
        self.stacking = None
        self.debate = None

    def load_models(self):
        """데이터 로드 + 모델 학습."""
        logger.info("Loading feature matrix...")
        self.features_df = pd.read_csv(self.features_path, low_memory=False)
        self.features_df["date"] = pd.to_datetime(self.features_df["date"])

        # 2001~2024로 학습 (2025는 예측 대상)
        train = self.features_df[self.features_df["season"] <= 2024].copy()
        y_train = train["home_win"]

        logger.info(f"Training on {len(train)} games (2001-2024)")

        # XGBoost
        self.xgb = XGBoostPredictor()
        self.xgb.fit(train, y_train)
        logger.info("XGBoost trained")

        # ELO — 학습 후 일일배치에서 갱신된 레이팅이 있으면 덮어쓰기
        self.elo = ELOPredictor(k=20, home_adv=20, reversion=0.3)
        self.elo.fit(train, y_train)
        elo_file = ROOT / "data" / "elo_ratings.json"
        if elo_file.exists():
            import json
            saved_elo = json.loads(elo_file.read_text(encoding="utf-8"))
            for team, rating in saved_elo.items():
                if team in self.elo.ratings:
                    self.elo.ratings[team]["elo"] = rating
                else:
                    self.elo.ratings[team] = {"elo": rating, "last_season": 2025}
            logger.info(f"ELO loaded from daily batch ({len(saved_elo)} teams)")
        else:
            logger.info("ELO trained from scratch")

        # EnsembleLGBM
        self.bay = BayesianPredictor(n_bootstrap=5)
        self.bay.fit(train, y_train)
        logger.info("EnsembleLGBM trained")

        # Stacking — valid set(2023-2024)에서 메타 러너 학습
        valid = self.features_df[self.features_df["season"].isin([2023, 2024])].copy()
        y_valid = valid["home_win"]
        if len(valid) > 0:
            import numpy as np
            xgb_vp = self.xgb.predict_proba(valid)
            bay_vp = self.bay.predict_proba(valid)
            # ELO valid용 별도 인스턴스
            elo_v = ELOPredictor(k=20, home_adv=20, reversion=0.3)
            elo_v.fit(train, y_train)
            elo_vp = elo_v.predict_and_update(valid)
            meta_valid = np.column_stack([xgb_vp, elo_vp, bay_vp])
            self.stacking = StackingPredictor()
            self.stacking.fit_meta(meta_valid, y_valid.values)
            logger.info("Stacking meta-learner trained")

        # 투수 스탯 DB (선발투수 조회용)
        pitcher_path = ROOT / "data" / "processed" / "pitching_2000_2025.csv"
        if pitcher_path.exists():
            self.pitcher_df = load_pitcher_data(pitcher_path)
            logger.info(f"Pitcher stats loaded ({len(self.pitcher_df)} records)")

        # 타자 스탯 DB (좌우 매치업 분석용)
        batting_path = ROOT / "data" / "processed" / "batting_2000_2025.csv"
        if batting_path.exists():
            self.batting_df = pd.read_csv(batting_path, encoding="utf-8-sig")
            logger.info(f"Batting stats loaded ({len(self.batting_df)} records)")

        # Debate pipeline
        self.debate = DebatePipeline(debate_rounds=self.debate_rounds)
        logger.info("Debate pipeline ready")

    def _get_team_context(self, team: str) -> dict:
        """팀의 최신 컨텍스트를 features_df에서 가져옴."""
        team = unify_team(team)
        # 가장 최근 경기에서 해당 팀의 데이터
        home_games = self.features_df[self.features_df["home_team"] == team]
        away_games = self.features_df[self.features_df["away_team"] == team]

        if not home_games.empty:
            latest = home_games.iloc[-1]
            return {
                "elo": latest.get("home_elo", 1500),
                "win_pct_10": latest.get("home_win_pct_10", 0.5),
                "streak": latest.get("home_streak", 0),
                "ops": latest.get("home_ops", 0),
                "era": latest.get("home_era", 0),
            }
        return {"elo": 1500, "win_pct_10": 0.5, "streak": 0, "ops": 0, "era": 0}

    def _build_live_features(self, home_team: str, away_team: str, date: str) -> pd.DataFrame:
        """피처 매트릭스에 없는 경기의 피처를 실시간 생성."""
        import json as _json
        from datetime import datetime as _dt

        # 기존 피처 매트릭스에서 최근 경기 기반 rolling stats 계산
        df = self.features_df
        all_games = df.sort_values("date")

        # 팀별 최근 경기에서 rolling stats 추출
        def get_team_rolling(team, side):
            if side == "home":
                team_games = all_games[all_games["home_team"] == team]
            else:
                team_games = all_games[all_games["away_team"] == team]
            # 홈/원정 무관하게 최근 경기
            as_home = all_games[all_games["home_team"] == team].tail(30)
            as_away = all_games[all_games["away_team"] == team].tail(30)
            return as_home, as_away

        home_h, home_a = get_team_rolling(home_team, "home")
        away_h, away_a = get_team_rolling(away_team, "away")

        # 최근 경기에서 피처값 가져오기 (가장 최근 행)
        feat = {}

        # 홈팀 — 마지막으로 홈으로 뛴 경기의 홈 피처 사용
        if not home_h.empty:
            last_h = home_h.iloc[-1]
            for col in ["home_win_pct_10", "home_win_pct_20", "home_win_pct_30",
                         "home_run_diff_10", "home_run_diff_20", "home_run_diff_30",
                         "home_runs_for_10", "home_runs_against_10",
                         "home_streak", "home_home_win_pct",
                         "home_elo", "home_ops", "home_era",
                         "home_sp_era", "home_sp_fip", "home_sp_war", "home_sp_whip",
                         "home_war", "home_war_pit", "home_wrc_plus",
                         "home_obp", "home_slg", "home_hr", "home_fip", "home_whip"]:
                feat[col] = last_h.get(col, np.nan)
        # 홈팀이 원정으로 뛴 최근 경기에서 보충
        if not home_a.empty and any(pd.isna(feat.get(c, np.nan)) for c in ["home_win_pct_10"]):
            last_a = home_a.iloc[-1]
            for hcol, acol in [("home_win_pct_10", "away_win_pct_10"),
                                ("home_run_diff_10", "away_run_diff_10"),
                                ("home_streak", "away_streak")]:
                if pd.isna(feat.get(hcol, np.nan)):
                    feat[hcol] = last_a.get(acol, np.nan)

        # 원정팀 — 마지막으로 원정으로 뛴 경기의 원정 피처
        if not away_h.empty:
            # 원정팀이 홈으로 뛴 경기도 참고
            last_away_as_away = all_games[all_games["away_team"] == away_team].tail(1)
            if not last_away_as_away.empty:
                last_aa = last_away_as_away.iloc[-1]
                for col in ["away_win_pct_10", "away_win_pct_20", "away_win_pct_30",
                             "away_run_diff_10", "away_run_diff_20", "away_run_diff_30",
                             "away_runs_for_10", "away_runs_against_10",
                             "away_streak", "away_away_win_pct",
                             "away_elo", "away_ops", "away_era",
                             "away_sp_era", "away_sp_fip", "away_sp_war", "away_sp_whip",
                             "away_war", "away_war_pit", "away_wrc_plus",
                             "away_obp", "away_slg", "away_hr", "away_fip", "away_whip"]:
                    feat[col] = last_aa.get(col, np.nan)

        # ELO — daily batch에서 갱신된 최신값 사용
        feat["home_elo"] = self.elo.ratings.get(home_team, {}).get("elo", 1500)
        feat["away_elo"] = self.elo.ratings.get(away_team, {}).get("elo", 1500)
        feat["elo_diff"] = feat["home_elo"] - feat["away_elo"]
        feat["elo_expected"] = 1 / (1 + 10 ** (-(feat["elo_diff"] + self.elo.home_adv) / 400))

        # h2h
        matchups = all_games[
            ((all_games["home_team"] == home_team) & (all_games["away_team"] == away_team)) |
            ((all_games["home_team"] == away_team) & (all_games["away_team"] == home_team))
        ].tail(10)
        if not matchups.empty:
            home_wins = sum(
                ((matchups["home_team"] == home_team) & (matchups["home_win"] == 1)) |
                ((matchups["away_team"] == home_team) & (matchups["home_win"] == 0))
            )
            feat["h2h_win_pct"] = home_wins / len(matchups)
            feat["h2h_count"] = len(matchups)
        else:
            feat["h2h_win_pct"] = 0.5
            feat["h2h_count"] = 0

        # 시간 피처
        try:
            dt = pd.Timestamp(date)
            feat["month"] = dt.month
            feat["day_of_week"] = dt.dayofweek
            feat["is_weekend"] = 1 if dt.dayofweek in [5, 6] else 0
            season_start = all_games[all_games["date"].dt.year == dt.year]["date"].min()
            feat["days_into_season"] = (dt - season_start).days if pd.notna(season_start) else 30
        except Exception:
            feat["month"] = 4
            feat["day_of_week"] = 0
            feat["is_weekend"] = 0
            feat["days_into_season"] = 30

        # 차이 피처
        for w in [10, 20, 30]:
            h_wp = feat.get(f"home_win_pct_{w}", 0.5)
            a_wp = feat.get(f"away_win_pct_{w}", 0.5)
            feat[f"win_pct_diff_{w}"] = (h_wp if pd.notna(h_wp) else 0.5) - (a_wp if pd.notna(a_wp) else 0.5)
            h_rd = feat.get(f"home_run_diff_{w}", 0)
            a_rd = feat.get(f"away_run_diff_{w}", 0)
            feat[f"run_diff_diff_{w}"] = (h_rd if pd.notna(h_rd) else 0) - (a_rd if pd.notna(a_rd) else 0)

        feat["ops_diff"] = feat.get("home_ops", 0.72) - feat.get("away_ops", 0.72)
        feat["era_diff"] = feat.get("away_era", 4.2) - feat.get("home_era", 4.2)
        feat["sp_era_diff"] = feat.get("away_sp_era", 4.2) - feat.get("home_sp_era", 4.2)
        feat["sp_war_diff"] = feat.get("home_sp_war", 0) - feat.get("away_sp_war", 0)
        feat["bat_war_diff"] = feat.get("home_war", 0) - feat.get("away_war", 0)
        feat["streak_diff"] = feat.get("home_streak", 0) - feat.get("away_streak", 0)
        feat["home_away_split_diff"] = feat.get("home_home_win_pct", 0.5) - feat.get("away_away_win_pct", 0.5)

        row = pd.DataFrame([feat])
        logger.info(f"  Live features generated for {away_team} @ {home_team} "
                     f"(elo_diff={feat['elo_diff']:.0f}, h_wp10={feat.get('home_win_pct_10', 'N/A')})")
        return row

    def predict_game(self, home_team: str, away_team: str, date: str,
                     extra_context: str = "",
                     home_starter: str = "",
                     away_starter: str = "",
                     home_team_raw: str = "",
                     away_team_raw: str = "") -> DebateResult:
        """단일 경기 예측 (ML + 에이전트 토론)."""
        # raw 팀명 보존 (CSV 조회용)
        if not home_team_raw:
            home_team_raw = home_team
        if not away_team_raw:
            away_team_raw = away_team
        home_team = unify_team(home_team)
        away_team = unify_team(away_team)

        # 해당 경기의 피처 행 찾기 (있으면)
        game_row = self.features_df[
            (self.features_df["home_team"] == home_team) &
            (self.features_df["away_team"] == away_team) &
            (self.features_df["date"].dt.strftime("%Y-%m-%d") == date)
        ]

        if not game_row.empty:
            row = game_row.iloc[[0]]
        else:
            # 피처 매트릭스에 없는 경기 → 실시간 피처 생성
            logger.info(f"  No feature row found — building live features")
            row = self._build_live_features(home_team, away_team, date)

        xgb_prob = float(self.xgb.predict_proba(row)[0])
        bay_prob = float(self.bay.predict_proba(row)[0])

        # ELO
        elo_home = self.elo.ratings.get(home_team, {}).get("elo", 1500)
        elo_away = self.elo.ratings.get(away_team, {}).get("elo", 1500)
        elo_prob = 1 / (1 + 10 ** ((elo_away - elo_home - self.elo.home_adv) / 400))

        # Stacking (AI 종합)
        import numpy as np
        ensemble_prob = float((xgb_prob + elo_prob + bay_prob) / 3)  # fallback
        if self.stacking:
            meta = np.array([[xgb_prob, elo_prob, bay_prob]])
            ensemble_prob = float(self.stacking.predict_proba_meta(meta)[0])

        # 팀 컨텍스트
        home_ctx = self._get_team_context(home_team)
        away_ctx = self._get_team_context(away_team)

        # h2h
        h2h = 0.5
        if not game_row.empty:
            h2h_val = game_row.iloc[0].get("h2h_win_pct")
            if pd.notna(h2h_val):
                h2h = float(h2h_val)

        # 자동 맥락 수집 (최근 경기, 시즌 성적, 선발투수 상세, AI 리서치)
        logger.info(f"Gathering context for {away_team} @ {home_team}...")
        auto_context = gather_full_context(
            home_team=home_team,
            away_team=away_team,
            date=date,
            features_df=self.features_df,
            include_web=True,
            home_starter=home_starter,
            away_starter=away_starter,
            home_team_raw=home_team_raw,
            away_team_raw=away_team_raw,
            pitcher_df=self.pitcher_df,
            batting_df=self.batting_df,
        )
        full_context = auto_context
        if extra_context:
            full_context += f"\n\n### 추가 정보 (사용자 입력)\n{extra_context}"

        # standings.json에서 순위 로드
        home_rank, away_rank = 0, 0
        standings_file = ROOT / "data" / "standings.json"
        if standings_file.exists():
            try:
                standings_data = json.loads(standings_file.read_text(encoding="utf-8"))
                teams_standings = standings_data.get("teams", {})
                ranked = sorted(teams_standings.items(),
                                key=lambda x: x[1].get("win_pct", 0), reverse=True)
                rank_map = {t: i + 1 for i, (t, _) in enumerate(ranked)}
                home_rank = rank_map.get(home_team, 0)
                away_rank = rank_map.get(away_team, 0)
            except (json.JSONDecodeError, KeyError):
                pass

        context = GameContext(
            home_team=home_team,
            away_team=away_team,
            date=date,
            xgboost_prob=xgb_prob,
            elo_prob=elo_prob,
            bayesian_prob=bay_prob,
            ensemble_prob=ensemble_prob,
            home_elo=elo_home,
            away_elo=elo_away,
            home_win_pct_10=home_ctx["win_pct_10"],
            away_win_pct_10=away_ctx["win_pct_10"],
            home_streak=int(home_ctx["streak"]),
            away_streak=int(away_ctx["streak"]),
            home_ops=home_ctx["ops"],
            away_ops=away_ctx["ops"],
            home_era=home_ctx["era"],
            away_era=away_ctx["era"],
            h2h_win_pct=h2h,
            home_rank=home_rank,
            away_rank=away_rank,
            extra_context=full_context,
        )

        result = self.debate.predict(context)
        return result

    def predict_games_batch(self, games: list[dict]) -> list[DebateResult]:
        """여러 경기를 일괄 예측."""
        results = []
        for game in games:
            result = self.predict_game(
                home_team=game["home_team"],
                away_team=game["away_team"],
                date=game["date"],
                extra_context=game.get("extra_context", ""),
            )
            results.append(result)
        return results


def demo():
    """데모 실행."""
    logging.basicConfig(level=logging.INFO, format="%(asctime)s [%(levelname)s] %(message)s")
    import sys
    sys.stdout.reconfigure(encoding="utf-8")

    predictor = GamePredictor(debate_rounds=2)
    predictor.load_models()

    # 2025 시즌 경기 예측 테스트
    result = predictor.predict_game(
        home_team="KIA",
        away_team="LG",
        date="2025-04-15",
    )

    print("\n" + "=" * 60)
    print("PREDICTION RESULT")
    print("=" * 60)
    print(f"Game: {result.away_team} @ {result.home_team}")
    print(f"Winner: {result.predicted_winner}")
    print(f"Home Win Prob: {result.home_win_probability:.3f}")
    print(f"Confidence: {result.confidence}")
    print(f"Key Factors: {result.key_factors}")
    print(f"Reasoning: {result.reasoning}")
    print(f"\nML Model Probs: {result.model_probabilities}")
    print(f"\nDebate Log ({len(result.debate_log)} entries):")
    for entry in result.debate_log:
        print(f"  [{entry['agent']} R{entry['round']}] prob={entry['probability']:.3f} ({entry['confidence']})")


if __name__ == "__main__":
    demo()
