"""ELO 레이팅 기반 경기 결과 예측 모델."""
import numpy as np
import pandas as pd
from .base import BasePredictor


class ELOPredictor(BasePredictor):
    """
    ELO 레이팅 시스템.

    FiveThirtyEight 방식 기반:
    - 시즌 간 평균 회귀 (30%)
    - 홈 어드밴티지 보정
    - 승차(margin) 기반 K-factor 조정
    """

    name = "elo"

    def __init__(self, k: int = 20, home_adv: float = 30, reversion: float = 0.3):
        self.k = k
        self.home_adv = home_adv
        self.reversion = reversion
        self.ratings = {}
        self._fitted = False

    def _expected(self, home_elo: float, away_elo: float) -> float:
        """홈팀 기대 승률."""
        return 1 / (1 + 10 ** ((away_elo - home_elo - self.home_adv) / 400))

    def _update(self, home: str, away: str, home_win: int, margin: int, season: int):
        """경기 결과로 ELO 업데이트."""
        for team in [home, away]:
            if team not in self.ratings:
                self.ratings[team] = {"elo": 1500, "last_season": season}
            if self.ratings[team]["last_season"] != season:
                self.ratings[team]["elo"] = (
                    self.ratings[team]["elo"] * (1 - self.reversion) + 1500 * self.reversion
                )
                self.ratings[team]["last_season"] = season

        home_elo = self.ratings[home]["elo"]
        away_elo = self.ratings[away]["elo"]
        expected = self._expected(home_elo, away_elo)

        elo_diff_winner = (home_elo - away_elo) if home_win == 1 else (away_elo - home_elo)
        margin_mult = np.log(abs(margin) + 1) * (2.2 / (elo_diff_winner * 0.001 + 2.2))
        update = self.k * margin_mult * (home_win - expected)

        self.ratings[home]["elo"] += update
        self.ratings[away]["elo"] -= update

    def fit(self, X: pd.DataFrame, y: pd.Series) -> None:
        """학습 데이터로 ELO 레이팅 구축."""
        self.ratings = {}
        for _, row in X.iterrows():
            margin = row["home_score"] - row["away_score"]
            season = int(row["season"])
            self._update(
                row["home_team"], row["away_team"],
                int(row["home_win"]), margin, season
            )
        self._fitted = True

    def predict_proba(self, X: pd.DataFrame) -> np.ndarray:
        """ELO 기반 홈팀 승리 확률."""
        probas = []
        for _, row in X.iterrows():
            home = row["home_team"]
            away = row["away_team"]
            home_elo = self.ratings.get(home, {}).get("elo", 1500)
            away_elo = self.ratings.get(away, {}).get("elo", 1500)
            probas.append(self._expected(home_elo, away_elo))
        return np.array(probas)

    def predict_and_update(self, X: pd.DataFrame) -> np.ndarray:
        """예측 후 결과로 ELO를 업데이트 (순차 예측용)."""
        probas = []
        for _, row in X.iterrows():
            home = row["home_team"]
            away = row["away_team"]
            season = int(row["season"])

            home_elo = self.ratings.get(home, {}).get("elo", 1500)
            away_elo = self.ratings.get(away, {}).get("elo", 1500)
            probas.append(self._expected(home_elo, away_elo))

            margin = row["home_score"] - row["away_score"]
            self._update(home, away, int(row["home_win"]), margin, season)

        return np.array(probas)

    def get_rankings(self) -> pd.DataFrame:
        """현재 ELO 순위."""
        data = [{"team": t, "elo": v["elo"]} for t, v in self.ratings.items()]
        return pd.DataFrame(data).sort_values("elo", ascending=False).reset_index(drop=True)
