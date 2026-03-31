"""예측 모델 베이스 클래스."""
from abc import ABC, abstractmethod
import numpy as np
import pandas as pd


class BasePredictor(ABC):
    """모든 예측 모델의 베이스 클래스."""

    name: str = "base"

    @abstractmethod
    def fit(self, X: pd.DataFrame, y: pd.Series) -> None:
        """모델 학습."""

    @abstractmethod
    def predict_proba(self, X: pd.DataFrame) -> np.ndarray:
        """홈팀 승리 확률 예측. shape: (n_samples,)"""

    def predict(self, X: pd.DataFrame, threshold: float = 0.5) -> np.ndarray:
        """이진 예측."""
        return (self.predict_proba(X) >= threshold).astype(int)

    def evaluate(self, X: pd.DataFrame, y: pd.Series) -> dict:
        """정확도, log loss, Brier score 평가."""
        from sklearn.metrics import accuracy_score, log_loss, brier_score_loss

        proba = self.predict_proba(X)
        preds = (proba >= 0.5).astype(int)

        return {
            "model": self.name,
            "accuracy": accuracy_score(y, preds),
            "log_loss": log_loss(y, proba),
            "brier_score": brier_score_loss(y, proba),
            "n_samples": len(y),
            "mean_pred": proba.mean(),
            "home_win_rate": y.mean(),
        }
