"""
모델 학습 및 평가 스크립트 v2.

변경사항:
  - game_features_v2.csv 사용 (미래정보 누수 없음)
  - XGBoost 정규화 강화
  - Bayesian을 LightGBM+bootstrap+calibration으로 교체
  - 가중 앙상블 추가
"""
import sys
from pathlib import Path

ROOT = Path(__file__).parent.parent
sys.path.insert(0, str(ROOT))

import pandas as pd
import numpy as np
from sklearn.metrics import log_loss, brier_score_loss

from backend.models.xgboost_model import XGBoostPredictor
from backend.models.elo_model import ELOPredictor
from backend.models.bayesian_model import BayesianPredictor


def main():
    sys.stdout.reconfigure(encoding="utf-8")

    # === 데이터 로드 ===
    df = pd.read_csv(ROOT / "data" / "features" / "game_features_v2.csv")
    df["date"] = pd.to_datetime(df["date"])
    print(f"Total games: {len(df)}")

    # === 분할 ===
    train = df[df["season"] <= 2022].copy()
    valid = df[df["season"].isin([2023, 2024])].copy()
    test = df[df["season"] == 2025].copy()

    print(f"Train: {len(train)} ({train['season'].min()}~{train['season'].max()})")
    print(f"Valid: {len(valid)} ({valid['season'].min()}~{valid['season'].max()})")
    print(f"Test:  {len(test)} ({test['season'].min()}~{test['season'].max()})")

    y_train = train["home_win"]
    y_valid = valid["home_win"]
    y_test = test["home_win"]

    # === 1. XGBoost ===
    print("\n" + "=" * 60)
    print("MODEL 1: XGBoost (regularized)")
    print("=" * 60)

    xgb_model = XGBoostPredictor()
    xgb_model.fit(train, y_train)

    xgb_train = xgb_model.evaluate(train, y_train)
    xgb_valid = xgb_model.evaluate(valid, y_valid)
    xgb_test = xgb_model.evaluate(test, y_test)

    print(f"  Train Acc: {xgb_train['accuracy']:.4f}  LogLoss: {xgb_train['log_loss']:.4f}")
    print(f"  Valid Acc: {xgb_valid['accuracy']:.4f}  LogLoss: {xgb_valid['log_loss']:.4f}")
    print(f"  Test  Acc: {xgb_test['accuracy']:.4f}  LogLoss: {xgb_test['log_loss']:.4f}")
    print(f"  Train-Test gap: {xgb_train['accuracy'] - xgb_test['accuracy']:.4f}")

    print("\n  Feature Importance (Top 15):")
    imp = xgb_model.feature_importance(15)
    for _, row in imp.iterrows():
        bar = "#" * int(row["importance"] * 200)
        print(f"    {row['feature']:30s} {row['importance']:.4f} {bar}")

    # === 2. ELO ===
    print("\n" + "=" * 60)
    print("MODEL 2: ELO")
    print("=" * 60)

    elo_model = ELOPredictor(k=20, home_adv=30, reversion=0.3)
    elo_model.fit(train, y_train)

    print("  ELO Rankings after training:")
    rankings = elo_model.get_rankings()
    for _, r in rankings.iterrows():
        print(f"    {r['team']:10s} {r['elo']:.0f}")

    elo_valid_model = ELOPredictor(k=20, home_adv=30, reversion=0.3)
    elo_valid_model.fit(train, y_train)
    elo_valid_proba = elo_valid_model.predict_and_update(valid)
    elo_valid_acc = ((elo_valid_proba >= 0.5).astype(int) == y_valid.values).mean()

    elo_test_proba = elo_valid_model.predict_and_update(test)
    elo_test_acc = ((elo_test_proba >= 0.5).astype(int) == y_test.values).mean()

    print(f"\n  Valid Acc: {elo_valid_acc:.4f}  LogLoss: {log_loss(y_valid, elo_valid_proba):.4f}")
    print(f"  Test  Acc: {elo_test_acc:.4f}  LogLoss: {log_loss(y_test, elo_test_proba):.4f}")

    # === 3. Bayesian (LightGBM + bootstrap + calibration) ===
    print("\n" + "=" * 60)
    print("MODEL 3: Bayesian (LightGBM+Bootstrap+Calibration)")
    print("=" * 60)

    bay_model = BayesianPredictor(n_bootstrap=10)
    bay_model.fit(train, y_train)

    bay_train = bay_model.evaluate(train, y_train)
    bay_valid = bay_model.evaluate(valid, y_valid)
    bay_test = bay_model.evaluate(test, y_test)

    print(f"  Train Acc: {bay_train['accuracy']:.4f}  LogLoss: {bay_train['log_loss']:.4f}")
    print(f"  Valid Acc: {bay_valid['accuracy']:.4f}  LogLoss: {bay_valid['log_loss']:.4f}")
    print(f"  Test  Acc: {bay_test['accuracy']:.4f}  LogLoss: {bay_test['log_loss']:.4f}")

    proba, uncertainty = bay_model.predict_with_uncertainty(test)
    print(f"\n  Test uncertainty: mean={uncertainty.mean():.4f}, std={uncertainty.std():.4f}")

    # 고확신 예측만 필터링
    high_conf = uncertainty < np.quantile(uncertainty, 0.25)
    if high_conf.sum() > 0:
        high_conf_acc = ((proba[high_conf] >= 0.5).astype(int) == y_test.values[high_conf]).mean()
        print(f"  High-confidence subset ({high_conf.sum()} games): Acc={high_conf_acc:.4f}")

    # === 요약 ===
    print("\n" + "=" * 60)
    print("SUMMARY — v1 vs v2")
    print("=" * 60)
    print(f"{'Model':<20} {'Valid Acc':>10} {'Test Acc':>10} {'Test LogLoss':>12}")
    print("-" * 55)
    print(f"{'Baseline':<20} {y_valid.mean():>10.4f} {y_test.mean():>10.4f} {'N/A':>12}")
    print(f"{'XGBoost':<20} {xgb_valid['accuracy']:>10.4f} {xgb_test['accuracy']:>10.4f} {xgb_test['log_loss']:>12.4f}")
    print(f"{'ELO':<20} {elo_valid_acc:>10.4f} {elo_test_acc:>10.4f} {log_loss(y_test, elo_test_proba):>12.4f}")
    print(f"{'Bayesian(LGB+Cal)':<20} {bay_valid['accuracy']:>10.4f} {bay_test['accuracy']:>10.4f} {bay_test['log_loss']:>12.4f}")

    # === 앙상블들 ===
    print("\n" + "=" * 60)
    print("ENSEMBLE COMPARISON")
    print("=" * 60)

    xgb_test_proba = xgb_model.predict_proba(test)
    bay_test_proba = bay_model.predict_proba(test)

    # 1. 단순 평균
    ens_simple = (xgb_test_proba + elo_test_proba + bay_test_proba) / 3
    ens_simple_acc = ((ens_simple >= 0.5).astype(int) == y_test.values).mean()
    ens_simple_ll = log_loss(y_test, ens_simple)

    # 2. 가중 평균 (검증 성능 기반)
    w_xgb = xgb_valid['accuracy']
    w_elo = elo_valid_acc
    w_bay = bay_valid['accuracy']
    w_total = w_xgb + w_elo + w_bay
    ens_weighted = (xgb_test_proba * w_xgb + elo_test_proba * w_elo + bay_test_proba * w_bay) / w_total
    ens_weighted_acc = ((ens_weighted >= 0.5).astype(int) == y_test.values).mean()
    ens_weighted_ll = log_loss(y_test, ens_weighted)

    # 3. XGBoost + ELO만 (가장 좋은 2개)
    ens_top2 = (xgb_test_proba + elo_test_proba) / 2
    ens_top2_acc = ((ens_top2 >= 0.5).astype(int) == y_test.values).mean()
    ens_top2_ll = log_loss(y_test, ens_top2)

    print(f"{'Ensemble':<25} {'Test Acc':>10} {'Test LogLoss':>12}")
    print("-" * 50)
    print(f"{'Simple Average (3)':<25} {ens_simple_acc:>10.4f} {ens_simple_ll:>12.4f}")
    print(f"{'Weighted Average (3)':<25} {ens_weighted_acc:>10.4f} {ens_weighted_ll:>12.4f}")
    print(f"{'Top 2 (XGB+ELO)':<25} {ens_top2_acc:>10.4f} {ens_top2_ll:>12.4f}")


if __name__ == "__main__":
    main()
