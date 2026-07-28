# ML 모델 명세

> **2026-07-28 실측 정정.** 이 문서가 기재하던 v4 62.9%는 **데이터 누수의 산물**이며
> 프로덕션에 존재한 적이 없다. 근거와 현재 실성능은 아래 [성능 이력](#성능-이력) 참조.

## Model A: XGBoost

| 항목 | 값 |
|------|-----|
| 클래스 | `XGBoostPredictor` |
| 파일 | `backend/models/xgboost_model.py` |
| 피처 수 | 59개 |
| n_estimators | 200 |
| max_depth | 3 |
| learning_rate | 0.03 |
| subsample | 0.7 |
| colsample_bytree | 0.6 |
| min_child_weight | 10 |
| reg_alpha (L1) | 0.5 |
| reg_lambda (L2) | 3.0 |
| gamma | 0.3 |
| CV 방식 | TimeSeriesSplit |
| Test 정확도 | **53.0%** (2025) / **54.5%** (2026) — 아래 성능 이력 참조 |

## Model B: ELO Rating

| 항목 | 값 |
|------|-----|
| 클래스 | `ELOPredictor` |
| 파일 | `backend/models/elo_model.py` |
| K-factor | 20 |
| 홈 어드밴티지 | 20점 |
| 시즌 회귀 | 30% → 1500 |
| 마진 보정 | `log(M+1) * (2.2 / (winner_elo_diff*0.001 + 2.2))` |
| Test 정확도 | **54.6%** (2025) / **52.5%** (2026) |

핵심 수식:
```
Expected = 1 / (1 + 10^((away - home - home_adv) / 400))
Update = K * margin_mult * (actual - expected)
```

## Model C: Ensemble LightGBM

| 항목 | 값 |
|------|-----|
| 클래스 | `EnsembleLGBMPredictor` |
| 파일 | `backend/models/bayesian_model.py` |
| 베이스 | LGBMClassifier |
| 부트스트랩 | 10회 (시즌 블록 단위) |
| 칼리브레이션 | Isotonic (CV=3) |
| 피처 수 | 30개 |
| 불확실성 | Bootstrap std |
| Test 정확도 | **51.4%** (2025) / **56.9%** (2026) |

## 성능 이력

### 실측 (2026-07-28, `game_features_v5.csv` / FEATURES 59개 = 현재 프로덕션 구성)

학습 2001–2024, 홀드아웃 2025·2026. `predict_proba` 직접 평가.

| 모델 | 2025 (n=698) | 2026 (n=459) | Brier (2026) |
|------|-------------|-------------|--------------|
| XGBoost | 53.0% | 54.5% | 0.2468 |
| EnsembleLGBM | 51.4% | 56.9% | 0.2494 |
| ELO | 54.6% | 52.5% | 0.2543 |
| "무조건 홈" 기준선 | 51.3% | 50.5% | 0.2512 |

두 시즌 모두 51–57% 대역이며, 어떤 모델도 기준선을 안정적으로 크게 앞서지 못한다.
ELO는 정확도 대비 Brier가 가장 나쁘다(확률 범위 0.199–0.808로 과신).

### v4 62.9%는 누수였다

v4의 `sp_*_actual` 12개 피처는 **시즌 최종 확정 스탯**이다. 2024시즌 8선발 이상
투수 40명 **전원(100%)** 의 `away_sp_era_actual`이 시즌 내내 단일 값 — 4월 경기가
그 투수의 10월 최종 ERA를 알고 있다. `docs/features.md`가 "해당 경기 전까지 누적"
이라고 적었던 것은 사실과 달랐다.

| v4 CSV, 동일 분할, 2025 테스트 | 정확도 | Brier |
|---|---|---|
| 59피처 (누수 없음) | 53.3% | 0.2484 |
| 59 + `_actual` 12개 | 62.3% | 0.2292 |
| └ 같은 모델의 **train** 정확도 | 62.65% | — |

train과 test의 격차가 없다. 과적합이면 벌어진다. 갭 없이 테스트 성능만 뛰는 것은
누수의 전형적 서명이다. 추론 시점에는 당일 선발의 시즌 최종 ERA를 알 수 없으므로
이 구성은 **재현 불가능**하다 — 복원하면 백테스트만 63%가 되고 실전은 53%에 머문다.

### 대체 경로

누수 없는 as-of 선발 스탯은 `backend/scrapers/kbo_pitching_log.py`가 수집하는
등판별 기록(이닝/자책/투구수/피안타/4사구/삼진)에서 경기 전날까지 누적해 만든다.
같은 원천으로 불펜 소진(최근 N일 투구수·연투)도 산출 가능하다.

### 이전 기재값 (검증 실패, 참고용)

| 버전 | XGBoost | ELO | LGBM | Stacking | 변경점 |
|------|---------|-----|------|----------|--------|
| v1 | 55.7% | 54.4% | 51.3% | - | 초기 (미래정보 누수) |
| v2 | 52.3% | 54.4% | 52.0% | - | 누수 수정, 전년도 스탯 |
| v3 | 59.9% | 54.4% | 59.6% | - | 원정 선발투수 개인 스탯 |
| v4 | 62.9% | 54.3% | 62.0% | 61.6% | 양쪽 선발투수 + Stacking + Optuna |

v3·v4 수치는 모두 `_actual` 누수 피처에 의존하므로 신뢰할 수 없다.

## 에이전트 모델 배정 (v2 — 3-provider)

| Agent | Model | Provider | 역할 | temp | 가격 (in/out) |
|-------|-------|----------|------|------|-------------|
| Analyst | Gemini 2.5 Pro | Google | 수학/추론, 통계 해석 | 0.4 | $1.25/$10 |
| Scout | GPT-4o | OpenAI | 한국어, KBO 도메인 지식 | 0.4 | $2.5/$10 |
| Critic | Claude Sonnet 4 | Anthropic | 비판적 사고, 반론 | 0.4 | $3/$15 |
| Synthesizer | Gemini 2.5 Flash | Google | JSON 종합, 최종 출력 | 0.1 | $0.15/$0.6 |

배정 근거: ReConcile (Chen et al. 2023) — 모델 다양성이 에이전트 수보다 중요.
3-provider(Google+OpenAI+Anthropic) 구성으로 학습 데이터/정렬 방법론의 다양성 확보.

## 결측치 기본값

```python
FILL_DEFAULTS = {
    h2h_win_pct: 0.5,       # 맞대결 없으면 동등
    home_era/away_era: 4.2,  # 리그 평균
    home_ops/away_ops: 0.72, # 리그 평균
    home_whip: 1.35,
    home_wrc_plus: 100.0,    # wRC+ 기준값
}
```
