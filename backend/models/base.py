"""예측 모델 베이스 클래스."""
from abc import ABC, abstractmethod
from datetime import datetime
from pathlib import Path
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
        return (self.predict_proba(X) >= threshold).astype(int)

    def evaluate(self, X: pd.DataFrame, y: pd.Series) -> dict:
        from sklearn.metrics import accuracy_score, log_loss, brier_score_loss, roc_auc_score
        from sklearn.calibration import calibration_curve

        proba = self.predict_proba(X)
        preds = (proba >= 0.5).astype(int)

        result = {
            "model": self.name,
            "accuracy": accuracy_score(y, preds),
            "log_loss": log_loss(y, proba),
            "brier_score": brier_score_loss(y, proba),
            "n_samples": len(y),
            "mean_pred": float(proba.mean()),
            "home_win_rate": float(y.mean()),
        }

        try:
            result["auc_roc"] = roc_auc_score(y, proba)
        except ValueError:
            result["auc_roc"] = None

        try:
            frac_pos, mean_pred = calibration_curve(y, proba, n_bins=10)
            result["calibration"] = {
                "fraction_positive": frac_pos.tolist(),
                "mean_predicted": mean_pred.tolist(),
            }
        except ValueError:
            result["calibration"] = None

        return result

    def save(self, path: str | Path) -> None:
        import joblib
        path = Path(path)
        path.parent.mkdir(parents=True, exist_ok=True)
        data = {
            "model": self,
            "metadata": {
                "name": self.name,
                "saved_at": datetime.now().isoformat(),
                "features": getattr(self, "features", []),
            },
        }
        joblib.dump(data, path)

    @classmethod
    def load(cls, path: str | Path):
        import joblib
        data = joblib.load(path)
        return data["model"]
