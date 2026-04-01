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
        self.xgb = None
        self.elo = None
        self.bay = None
        self.stacking = None
        self.debate = None

    def load_models(self):
        """데이터 로드 + 모델 학습."""
        logger.info("Loading feature matrix...")
        self.features_df = pd.read_csv(self.features_path)
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
            xgb_prob = float(self.xgb.predict_proba(row)[0])
            bay_prob = float(self.bay.predict_proba(row)[0])
        else:
            # 피처 데이터가 없으면 기본값
            xgb_prob = 0.5
            bay_prob = 0.5

        # ELO
        elo_home = self.elo.ratings.get(home_team, {}).get("elo", 1500)
        elo_away = self.elo.ratings.get(away_team, {}).get("elo", 1500)
        elo_prob = 1 / (1 + 10 ** ((elo_away - elo_home - 30) / 400))

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
        )
        full_context = auto_context
        if extra_context:
            full_context += f"\n\n### 추가 정보 (사용자 입력)\n{extra_context}"

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
