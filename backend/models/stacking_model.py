"""Stacking 앙상블 — LogisticRegression 메타 러너."""
import numpy as np
import pandas as pd
from sklearn.linear_model import LogisticRegression
from sklearn.preprocessing import StandardScaler
from .base import BasePredictor


class StackingPredictor(BasePredictor):
    """3개 베이스 모델의 확률 출력을 메타 러너로 종합."""

    name = "stacking"

    def __init__(self):
        self.meta_model = LogisticRegression(max_iter=1000, C=1.0)
        self.scaler = StandardScaler()
        self._fitted = False

    def fit_meta(self, base_probas: np.ndarray, y: np.ndarray) -> None:
        """
        메타 러너 학습.

        Args:
            base_probas: shape (n_samples, 3) — [xgb_prob, elo_prob, lgbm_prob]
            y: 실제 결과
        """
        # 메타 피처: 원래 확률 + 차이/분산
        X_meta = self._build_meta_features(base_probas)
        X_scaled = self.scaler.fit_transform(X_meta)
        self.meta_model.fit(X_scaled, y)
        self._fitted = True

    def predict_proba_meta(self, base_probas: np.ndarray) -> np.ndarray:
        """메타 러너로 최종 확률 예측."""
        X_meta = self._build_meta_features(base_probas)
        X_scaled = self.scaler.transform(X_meta)
        return self.meta_model.predict_proba(X_scaled)[:, 1]

    def _build_meta_features(self, probas: np.ndarray) -> np.ndarray:
        """베이스 확률에서 메타 피처 생성."""
        # probas shape: (n, 3)
        mean = probas.mean(axis=1, keepdims=True)
        std = probas.std(axis=1, keepdims=True)
        max_min_diff = (probas.max(axis=1, keepdims=True) - probas.min(axis=1, keepdims=True))
        return np.hstack([probas, mean, std, max_min_diff])

    # BasePredictor 인터페이스 (단독 사용 시)
    def fit(self, X: pd.DataFrame, y: pd.Series) -> None:
        pass  # fit_meta 사용

    def predict_proba(self, X: pd.DataFrame) -> np.ndarray:
        pass  # predict_proba_meta 사용
