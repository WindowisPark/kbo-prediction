"""
앙상블 LightGBM 예측 모델 — Bootstrap + Isotonic Calibration.

LightGBM으로 예측력 확보 + isotonic regression으로 확률 보정.
불확실성은 bootstrap 앙상블의 분산으로 추정.
"""
import numpy as np
import pandas as pd
import lightgbm as lgb
from sklearn.calibration import CalibratedClassifierCV
from .base import BasePredictor

FEATURES = [
    "elo_diff", "elo_expected",
    "win_pct_diff_10", "run_diff_diff_10",
    "win_pct_diff_20", "run_diff_diff_20",
    "win_pct_diff_30", "run_diff_diff_30",
    "ops_diff", "era_diff",
    "sp_era_diff", "sp_war_diff",
    "bat_war_diff", "streak_diff",
    "home_streak", "away_streak",
    "h2h_win_pct", "h2h_count",
    "home_home_win_pct", "away_away_win_pct",
    "home_away_split_diff",
    "is_weekend", "month", "days_into_season",
    "home_wrc_plus", "away_wrc_plus",
    "home_runs_for_10", "away_runs_for_10",
    "home_runs_against_10", "away_runs_against_10",
]

FILL_DEFAULTS = {
    "h2h_win_pct": 0.5, "home_home_win_pct": 0.5, "away_away_win_pct": 0.5,
    "home_era": 4.2, "away_era": 4.2, "home_sp_era": 4.2, "away_sp_era": 4.2,
    "home_ops": 0.720, "away_ops": 0.720,
    "home_whip": 1.35, "away_whip": 1.35,
    "home_wrc_plus": 100.0, "away_wrc_plus": 100.0,
}


class EnsembleLGBMPredictor(BasePredictor):
    """LightGBM + Bootstrap + Isotonic Calibration 앙상블."""

    name = "ensemble_lgbm"

    def __init__(self, n_bootstrap: int = 10):
        self.n_bootstrap = n_bootstrap
        self.models = []
        self.features = FEATURES

    def _base_model(self):
        return lgb.LGBMClassifier(
            n_estimators=150, max_depth=3, learning_rate=0.05,
            subsample=0.7, colsample_bytree=0.7, min_child_samples=20,
            reg_alpha=0.3, reg_lambda=2.0, random_state=42, verbose=-1,
        )

    def _prepare(self, X: pd.DataFrame) -> pd.DataFrame:
        available = [f for f in self.features if f in X.columns]
        result = X[available].copy()
        for col, default in FILL_DEFAULTS.items():
            if col in result.columns:
                result[col] = result[col].fillna(default)
        return result.fillna(0)

    def fit(self, X: pd.DataFrame, y: pd.Series) -> None:
        X_prep = self._prepare(X)
        y_arr = y.values
        self.models = []
        rng = np.random.RandomState(42)

        # 시즌 기반 block bootstrap (시계열 구조 보존)
        has_season = "season" in X.columns
        if has_season:
            seasons = X["season"].values

        for i in range(self.n_bootstrap):
            if has_season:
                unique_seasons = np.unique(seasons)
                sampled = rng.choice(unique_seasons, size=len(unique_seasons), replace=True)
                indices = np.concatenate([np.where(seasons == s)[0] for s in sampled])
            else:
                indices = rng.choice(len(X_prep), size=len(X_prep), replace=True)

            X_boot = X_prep.iloc[indices].reset_index(drop=True)
            y_boot = y_arr[indices]

            model = self._base_model()
            model.set_params(random_state=42 + i)
            # cv=3: bootstrap 내에서는 시간 순서가 섞이므로 KFold 허용
            calibrated = CalibratedClassifierCV(model, method="isotonic", cv=3)
            calibrated.fit(X_boot, y_boot)
            self.models.append(calibrated)

    def predict_proba(self, X: pd.DataFrame) -> np.ndarray:
        X_prep = self._prepare(X)
        all_probas = np.array([m.predict_proba(X_prep)[:, 1] for m in self.models])
        return all_probas.mean(axis=0)

    def predict_with_uncertainty(self, X: pd.DataFrame) -> tuple[np.ndarray, np.ndarray]:
        X_prep = self._prepare(X)
        all_probas = np.array([m.predict_proba(X_prep)[:, 1] for m in self.models])
        return all_probas.mean(axis=0), all_probas.std(axis=0)

    def feature_weights(self) -> pd.DataFrame:
        base = self.models[0].estimators_[0]
        names = base.feature_name_ if hasattr(base, 'feature_name_') else [f"f{i}" for i in range(len(base.feature_importances_))]
        return pd.DataFrame({
            "feature": names,
            "importance": base.feature_importances_,
        }).sort_values("importance", ascending=False)


# 하위 호환 alias
BayesianPredictor = EnsembleLGBMPredictor
