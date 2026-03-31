"""XGBoost 기반 경기 결과 예측 모델 v2."""
import numpy as np
import pandas as pd
import xgboost as xgb
from sklearn.model_selection import cross_val_score, TimeSeriesSplit
from .base import BasePredictor

FILL_DEFAULTS = {
    "h2h_win_pct": 0.5, "home_home_win_pct": 0.5, "away_away_win_pct": 0.5,
    "home_era": 4.2, "away_era": 4.2, "home_sp_era": 4.2, "away_sp_era": 4.2,
    "home_ops": 0.720, "away_ops": 0.720,
    "home_whip": 1.35, "away_whip": 1.35,
    "home_wrc_plus": 100.0, "away_wrc_plus": 100.0,
}

FEATURES = [
    # Rolling stats
    "home_win_pct_10", "away_win_pct_10",
    "home_run_diff_10", "away_run_diff_10",
    "home_runs_for_10", "away_runs_for_10",
    "home_runs_against_10", "away_runs_against_10",
    "home_win_pct_20", "away_win_pct_20",
    "home_run_diff_20", "away_run_diff_20",
    "home_win_pct_30", "away_win_pct_30",
    "home_run_diff_30", "away_run_diff_30",
    "home_streak", "away_streak",

    # 홈/원정 분리 승률
    "home_home_win_pct", "away_away_win_pct",

    # 상대전적
    "h2h_win_pct", "h2h_count",

    # ELO
    "home_elo", "away_elo", "elo_diff", "elo_expected",

    # 전년도 팀 스탯 (누수 없음)
    "home_ops", "away_ops",
    "home_era", "away_era",
    "home_sp_era", "away_sp_era",
    "home_sp_fip", "away_sp_fip",
    "home_sp_war", "away_sp_war",
    "home_war", "away_war",        # 타자 WAR
    "home_war_pit", "away_war_pit",
    "home_wrc_plus", "away_wrc_plus",

    # 차이 피처
    "win_pct_diff_10", "run_diff_diff_10",
    "win_pct_diff_20", "run_diff_diff_20",
    "win_pct_diff_30", "run_diff_diff_30",
    "ops_diff", "era_diff",
    "sp_era_diff", "sp_war_diff",
    "bat_war_diff", "streak_diff",
    "home_away_split_diff",

    # 시간
    "month", "day_of_week", "is_weekend", "days_into_season",
]


class XGBoostPredictor(BasePredictor):
    """XGBoost 경기 결과 예측 — 과적합 해소 버전."""

    name = "xgboost"

    def __init__(self, **kwargs):
        params = {
            "n_estimators": 200,
            "max_depth": 3,              # 4→3: 복잡도 제한
            "learning_rate": 0.03,       # 0.05→0.03: 더 보수적
            "subsample": 0.7,            # 0.8→0.7
            "colsample_bytree": 0.6,     # 0.8→0.6: 피처 랜덤 선택 강화
            "min_child_weight": 10,      # 5→10: 더 큰 리프
            "reg_alpha": 0.5,            # 0.1→0.5: L1 정규화 강화
            "reg_lambda": 3.0,           # 1.0→3.0: L2 정규화 강화
            "gamma": 0.3,               # 분할 최소 손실 감소
            "max_delta_step": 1,         # 로지스틱에서 불균형 완화
            "objective": "binary:logistic",
            "eval_metric": "logloss",
            "random_state": 42,
        }
        params.update(kwargs)
        self.model = xgb.XGBClassifier(**params)
        self.features = FEATURES

    def _prepare(self, X: pd.DataFrame) -> pd.DataFrame:
        available = [f for f in self.features if f in X.columns]
        result = X[available].copy()
        for col, default in FILL_DEFAULTS.items():
            if col in result.columns:
                result[col] = result[col].fillna(default)
        return result.fillna(0)

    def fit(self, X: pd.DataFrame, y: pd.Series) -> None:
        X_prep = self._prepare(X)
        self.model.fit(X_prep, y)

    def predict_proba(self, X: pd.DataFrame) -> np.ndarray:
        X_prep = self._prepare(X)
        return self.model.predict_proba(X_prep)[:, 1]

    def feature_importance(self, top_n: int = 20) -> pd.DataFrame:
        imp = pd.DataFrame({
            "feature": self.model.get_booster().feature_names,
            "importance": self.model.feature_importances_,
        }).sort_values("importance", ascending=False)
        return imp.head(top_n)

    def cross_validate(self, X: pd.DataFrame, y: pd.Series, cv: int = 5) -> dict:
        X_prep = self._prepare(X)
        tscv = TimeSeriesSplit(n_splits=cv)
        scores = cross_val_score(self.model, X_prep, y, cv=tscv, scoring="accuracy")
        return {
            "cv_mean": scores.mean(),
            "cv_std": scores.std(),
            "cv_scores": scores.tolist(),
        }
