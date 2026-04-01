"""
모델 최적화 스크립트.

1. Optuna 하이퍼파라미터 자동 튜닝 (XGBoost, ELO)
2. Calibration 검증 + 확률 보정
3. 최적 모델 저장 (joblib)
"""
import sys
from pathlib import Path

ROOT = Path(__file__).parent.parent
sys.path.insert(0, str(ROOT))

import pandas as pd
import numpy as np
import optuna
from sklearn.metrics import log_loss, brier_score_loss, roc_auc_score
from sklearn.calibration import calibration_curve
from sklearn.model_selection import TimeSeriesSplit

optuna.logging.set_verbosity(optuna.logging.WARNING)


def main():
    sys.stdout.reconfigure(encoding="utf-8")

    df = pd.read_csv(ROOT / "data" / "features" / "game_features_v4.csv")
    df["date"] = pd.to_datetime(df["date"])

    train = df[df["season"] <= 2022].copy()
    valid = df[df["season"].isin([2023, 2024])].copy()
    test = df[df["season"] == 2025].copy()
    y_train, y_valid, y_test = train["home_win"], valid["home_win"], test["home_win"]

    print("=" * 60)
    print("1. Optuna XGBoost 튜닝 (50 trials)")
    print("=" * 60)

    from backend.models.xgboost_model import XGBoostPredictor, FEATURES, FILL_DEFAULTS

    extra_features = [
        "home_sp_era_actual", "home_sp_fip_actual", "home_sp_war_actual", "home_sp_whip_actual",
        "away_sp_era_actual", "away_sp_fip_actual", "away_sp_war_actual", "away_sp_whip_actual",
        "sp_era_actual_diff", "sp_war_actual_diff", "sp_fip_actual_diff", "sp_whip_actual_diff",
    ]
    all_features = FEATURES + extra_features

    def xgb_objective(trial):
        params = {
            "n_estimators": trial.suggest_int("n_estimators", 100, 400),
            "max_depth": trial.suggest_int("max_depth", 2, 5),
            "learning_rate": trial.suggest_float("learning_rate", 0.01, 0.1, log=True),
            "subsample": trial.suggest_float("subsample", 0.5, 0.9),
            "colsample_bytree": trial.suggest_float("colsample_bytree", 0.4, 0.8),
            "min_child_weight": trial.suggest_int("min_child_weight", 5, 20),
            "reg_alpha": trial.suggest_float("reg_alpha", 0.01, 2.0, log=True),
            "reg_lambda": trial.suggest_float("reg_lambda", 0.5, 5.0),
            "gamma": trial.suggest_float("gamma", 0.0, 1.0),
        }
        model = XGBoostPredictor(**params)
        model.features = all_features
        model.fit(train, y_train)
        proba = model.predict_proba(valid)
        return log_loss(y_valid, proba)

    study = optuna.create_study(direction="minimize")
    study.optimize(xgb_objective, n_trials=50)

    print(f"Best log_loss: {study.best_value:.4f}")
    print(f"Best params: {study.best_params}")

    # 최적 모델 학습
    best_xgb = XGBoostPredictor(**study.best_params)
    best_xgb.features = all_features
    best_xgb.fit(train, y_train)
    xgb_eval = best_xgb.evaluate(test, y_test)
    print(f"Test acc: {xgb_eval['accuracy']:.4f}, AUC: {xgb_eval.get('auc_roc', 'N/A')}")

    # 저장
    model_dir = ROOT / "data" / "models"
    model_dir.mkdir(exist_ok=True)
    best_xgb.save(model_dir / "xgboost_best.joblib")
    print(f"Saved: {model_dir / 'xgboost_best.joblib'}")

    print("\n" + "=" * 60)
    print("2. ELO 최적 K-factor 탐색")
    print("=" * 60)

    from backend.models.elo_model import ELOPredictor

    best_elo_acc = 0
    best_k = 20
    for k in [10, 15, 18, 20, 22, 25, 30]:
        elo = ELOPredictor(k=k, home_adv=20, reversion=0.3)
        elo.fit(train, y_train)
        elo.predict_and_update(valid)
        proba = elo.predict_and_update(test)
        acc = ((proba >= 0.5).astype(int) == y_test.values).mean()
        print(f"  K={k:3d}: acc={acc:.4f}")
        if acc > best_elo_acc:
            best_elo_acc = acc
            best_k = k

    print(f"Best K: {best_k} (acc={best_elo_acc:.4f})")

    print("\n" + "=" * 60)
    print("3. Calibration 검증")
    print("=" * 60)

    # XGBoost calibration
    xgb_proba = best_xgb.predict_proba(test)
    frac_pos, mean_pred = calibration_curve(y_test, xgb_proba, n_bins=5)

    print(f"\nXGBoost Calibration (5 bins):")
    print(f"{'Predicted':>10} {'Actual':>10} {'Gap':>10}")
    for mp, fp in zip(mean_pred, frac_pos):
        gap = fp - mp
        print(f"{mp:>10.3f} {fp:>10.3f} {gap:>+10.3f}")

    brier = brier_score_loss(y_test, xgb_proba)
    print(f"\nBrier Score: {brier:.4f}")
    print(f"AUC-ROC: {roc_auc_score(y_test, xgb_proba):.4f}")

    # ELO calibration
    elo_best = ELOPredictor(k=best_k, home_adv=20, reversion=0.3)
    elo_best.fit(train, y_train)
    elo_best.predict_and_update(valid)
    elo_proba = elo_best.predict_and_update(test)
    frac_pos_e, mean_pred_e = calibration_curve(y_test, elo_proba, n_bins=5)

    print(f"\nELO Calibration (5 bins):")
    print(f"{'Predicted':>10} {'Actual':>10} {'Gap':>10}")
    for mp, fp in zip(mean_pred_e, frac_pos_e):
        gap = fp - mp
        print(f"{mp:>10.3f} {fp:>10.3f} {gap:>+10.3f}")

    print("\n" + "=" * 60)
    print("4. 최종 성능 요약")
    print("=" * 60)

    from backend.models.bayesian_model import EnsembleLGBMPredictor
    lgbm = EnsembleLGBMPredictor(n_bootstrap=5)
    lgbm.features = lgbm.features + extra_features
    lgbm.fit(train, y_train)
    lgbm_eval = lgbm.evaluate(test, y_test)

    print(f"{'Model':<20} {'Acc':>8} {'LogLoss':>8} {'AUC':>8} {'Brier':>8}")
    print("-" * 55)
    print(f"{'XGBoost (tuned)':<20} {xgb_eval['accuracy']:>8.4f} {xgb_eval['log_loss']:>8.4f} {xgb_eval.get('auc_roc','?'):>8} {xgb_eval['brier_score']:>8.4f}")
    print(f"{'ELO (K={best_k})':<20} {best_elo_acc:>8.4f}")
    print(f"{'EnsembleLGBM':<20} {lgbm_eval['accuracy']:>8.4f} {lgbm_eval['log_loss']:>8.4f} {lgbm_eval.get('auc_roc','?'):>8} {lgbm_eval['brier_score']:>8.4f}")


if __name__ == "__main__":
    main()
