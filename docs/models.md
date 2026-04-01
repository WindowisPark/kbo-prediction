# ML 모델 명세

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
| Test 정확도 | **59.9%** (v3) |

## Model B: ELO Rating

| 항목 | 값 |
|------|-----|
| 클래스 | `ELOPredictor` |
| 파일 | `backend/models/elo_model.py` |
| K-factor | 20 |
| 홈 어드밴티지 | 30점 |
| 시즌 회귀 | 30% → 1500 |
| 마진 보정 | `log(M+1) * (2.2 / (winner_elo_diff*0.001 + 2.2))` |
| Test 정확도 | **54.4%** |

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
| Test 정확도 | **59.6%** |

## 성능 이력

| 버전 | XGBoost | ELO | LGBM | 변경점 |
|------|---------|-----|------|--------|
| v1 | 55.7% | 54.4% | 51.3% | 초기 (미래정보 누수) |
| v2 | 52.3% | 54.4% | 52.0% | 누수 수정, 전년도 스탯 |
| v3 | **59.9%** | 54.4% | **59.6%** | 선발투수 개인 스탯 |

## 피처 중요도 Top 10 (v3)

| 순위 | 피처 | 중요도 |
|------|------|--------|
| 1 | sp_war_actual_diff | 0.065 |
| 2 | away_sp_war_actual | 0.035 |
| 3 | sp_era_actual_diff | 0.034 |
| 4 | elo_diff | 0.030 |
| 5 | elo_expected | 0.029 |
| 6 | away_sp_whip_actual | 0.026 |
| 7 | away_sp_era_actual | 0.024 |
| 8 | run_diff_diff_20 | 0.023 |
| 9 | run_diff_diff_30 | 0.021 |
| 10 | bat_war_diff | 0.020 |

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
