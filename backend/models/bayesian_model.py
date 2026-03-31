"""
베이지안 예측 모델 v2 — Gaussian Process 기반.

v1의 BayesianRidge가 거의 선형이라 성능이 베이스라인 수준이었음.
v2는 LightGBM + 칼리브레이션으로 교체하되, 불확실성은
예측 분포의 분산으로 추정.
"""
import numpy as np
import pandas as pd
import lightgbm as lgb
from sklearn.calibration import CalibratedClassifierCV
from sklearn.model_selection import cross_val_predict
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


class BayesianPredictor(BasePredictor):
    """
    LightGBM + Isotonic 칼리브레이션.

    LightGBM으로 예측력 확보 + isotonic regression으로 확률 보정.
    불확실성은 bootstrap 앙상블의 분산으로 추정.
    """

    name = "bayesian"

    def __init__(self, n_bootstrap: int = 10):
        self.n_bootstrap = n_bootstrap
        self.models = []
        self.features = FEATURES

    def _base_model(self):
        return lgb.LGBMClassifier(
            n_estimators=150,
            max_depth=3,
            learning_rate=0.05,
            subsample=0.7,
            colsample_bytree=0.7,
            min_child_samples=20,
            reg_alpha=0.3,
            reg_lambda=2.0,
            random_state=42,
            verbose=-1,
        )

    def _prepare(self, X: pd.DataFrame) -> pd.DataFrame:
        available = [f for f in self.features if f in X.columns]
        return X[available].fillna(0)

    def fit(self, X: pd.DataFrame, y: pd.Series) -> None:
        X_prep = self._prepare(X)
        y_arr = y.values

        self.models = []
        rng = np.random.RandomState(42)

        for i in range(self.n_bootstrap):
            # Bootstrap 샘플링
            indices = rng.choice(len(X_prep), size=len(X_prep), replace=True)
            X_boot = X_prep.iloc[indices].reset_index(drop=True)
            y_boot = y_arr[indices]

            model = self._base_model()
            model.set_params(random_state=42 + i)
            calibrated = CalibratedClassifierCV(model, method="isotonic", cv=3)
            calibrated.fit(X_boot, y_boot)
            self.models.append(calibrated)

    def predict_proba(self, X: pd.DataFrame) -> np.ndarray:
        X_prep = self._prepare(X)
        all_probas = np.array([m.predict_proba(X_prep)[:, 1] for m in self.models])
        return all_probas.mean(axis=0)

    def predict_with_uncertainty(self, X: pd.DataFrame) -> tuple[np.ndarray, np.ndarray]:
        """예측 + 불확실성(bootstrap 분산)."""
        X_prep = self._prepare(X)
        all_probas = np.array([m.predict_proba(X_prep)[:, 1] for m in self.models])
        return all_probas.mean(axis=0), all_probas.std(axis=0)

    def feature_weights(self) -> pd.DataFrame:
        """첫 번째 모델의 피처 중요도."""
        base = self.models[0].estimators_[0]
        available = [f for f in self.features if f in self.features]
        imp = base.feature_importances_
        return pd.DataFrame({
            "feature": available[:len(imp)],
            "importance": imp,
        }).sort_values("importance", ascending=False)
