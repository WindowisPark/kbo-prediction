# KBO AI Predictor

KBO(한국프로야구) 경기 결과를 예측하는 AI 시스템.
3개 ML 모델의 수치 예측 + Claude/GPT 멀티 에이전트 토론을 결합한 하이브리드 아키텍처.

## Architecture

```
[KBO 공식 사이트] ──→ [데이터 수집 파이프라인]
                              │
                    ┌─────────┴─────────┐
                    │                   │
              [피처 엔지니어링]    [Context Gatherer]
                    │                   │
            ┌───────┼───────┐    ┌──────┼──────┐
            │       │       │    │      │      │
         XGBoost   ELO  Bayesian │   선발투수   AI리서치
            │       │       │    │   스탯조회   (GPT-4o)
            └───────┼───────┘    │   용병/신인  │
                    │            │   자동판별   │
                    ▼            └──────┼──────┘
              승률% 출력                │
                    │                   │
                    ▼                   ▼
         ┌──────────────────────────────────┐
         │   Multi-Agent Debate Pipeline    │
         │                                  │
         │  Analyst (GPT-4o)    ──┐         │
         │  Scout   (Claude)    ──┤ 2 Rounds│
         │  Critic  (GPT-4-turbo)─┘         │
         │           │                      │
         │  Synthesizer (GPT-4o)            │
         └──────────┬───────────────────────┘
                    │
                    ▼
              최종 예측 + 근거
```

## Features

- **ML 모델 3종**: XGBoost, ELO 레이팅, Bayesian (LightGBM+Bootstrap+Calibration)
- **멀티 모델 에이전트 토론**: Claude + GPT가 서로 다른 관점에서 토론 (ReConcile 방식)
- **자동 맥락 수집**: 최근 경기 결과, 시즌 성적, 상대전적, 선발투수 개인 스탯
- **외국인/신인 자동 판별**: 데뷔 시즌 용병의 KBO 적응 불확실성 반영
- **실시간 경기 일정**: KBO 공식 사이트에서 당일 경기 + 선발투수 자동 수집
- **날짜 네비게이션**: 과거/미래 경기 일정 조회 및 과거 결과 확인
- **일일 배치**: ELO 갱신, 적중률 추적, 데이터셋 자동 업데이트
- **병렬 예측**: 5경기 동시 예측 가능 (ThreadPoolExecutor)

## Tech Stack

| Layer | Tech |
|-------|------|
| Frontend | Next.js 16 + Tailwind CSS |
| Backend API | FastAPI + Uvicorn |
| ML Models | XGBoost, LightGBM, scikit-learn |
| LLM Agents | Anthropic Claude API + OpenAI GPT API |
| Data Source | KBO 공식 사이트 (koreabaseball.com) |
| Data | Kaggle + KBO 공식 API 스크래핑 |

## Project Structure

```
kbo-prediction/
├── backend/
│   ├── agents/           # 멀티 에이전트 토론 파이프라인
│   │   ├── debate.py         # 토론 엔진 (Phase 1/2/3)
│   │   ├── predictor.py      # ML + 에이전트 통합 예측기
│   │   ├── context_gatherer.py  # 자동 맥락 수집
│   │   ├── llm_clients.py    # Claude/GPT 통합 클라이언트
│   │   └── prompts.py        # 에이전트 시스템 프롬프트
│   ├── api/              # FastAPI 엔드포인트
│   │   ├── app.py
│   │   └── schemas.py
│   ├── features/         # 피처 엔지니어링
│   │   └── build_features.py
│   ├── models/           # ML 모델
│   │   ├── xgboost_model.py
│   │   ├── elo_model.py
│   │   └── bayesian_model.py
│   ├── scrapers/         # 데이터 수집
│   │   ├── kbo_game_scraper.py
│   │   ├── kbo_stats_scraper.py
│   │   ├── kbo_today.py
│   │   ├── kbo_lineup.py
│   │   └── kbo_starter_scraper.py
│   └── utils/
│       ├── team_mapping.py
│       └── player_stats.py   # 선수 스탯 조회 + 용병/신인 판별
├── frontend-app/         # Next.js 프론트엔드
│   └── src/app/
│       ├── page.tsx          # 메인 대시보드
│       ├── standings/        # ELO 순위
│       └── history/          # 예측 이력
├── scripts/
│   ├── daily_batch.py    # 일일 배치 (ELO 갱신 + 적중률)
│   ├── train_evaluate.py # 모델 학습/평가
│   ├── collect_all.py    # 데이터 전체 수집
│   └── download_kaggle.py
├── data/
│   ├── raw/              # 원본 데이터 (CSV)
│   ├── processed/        # 전처리된 데이터
│   └── features/         # 피처 매트릭스
├── config/
│   ├── settings.py
│   └── db_schema.sql
└── notebooks/
```

## Quick Start

### 1. 환경 설정

```bash
git clone https://github.com/YOUR_USERNAME/kbo-prediction.git
cd kbo-prediction
pip install -r requirements.txt
cp .env.example .env
# .env에 API 키 설정:
#   ANTHROPIC_API_KEY=sk-ant-...
#   OPENAI_API_KEY=sk-proj-...
```

### 2. 데이터 수집

```bash
# Kaggle 데이터셋 다운로드
python scripts/download_kaggle.py

# KBO 공식 사이트에서 경기 결과 스크래핑 (2001~2025)
python scripts/collect_all.py --skip-kaggle
```

### 3. 피처 엔지니어링 + 모델 학습

```bash
# 피처 매트릭스 생성
python backend/features/build_features.py

# 모델 학습 및 평가
python scripts/train_evaluate.py
```

### 4. 서버 실행

```bash
# 백엔드 (포트 8000)
python -m uvicorn backend.api.app:app --host 0.0.0.0 --port 8000

# 프론트엔드 (포트 3000)
cd frontend-app && npm install && npm run dev
```

### 5. 일일 배치

```bash
# 어제 경기 결과 반영 + ELO 갱신 + 적중률 업데이트
python scripts/daily_batch.py

# 특정 날짜 처리
python scripts/daily_batch.py --date 20260401
```

## API Endpoints

| Method | Path | Description |
|--------|------|-------------|
| GET | `/` | 헬스체크 |
| GET | `/today?date=YYYYMMDD` | 경기 일정 (선발투수 포함) |
| POST | `/predict` | 단일 경기 예측 |
| POST | `/today/predict` | 당일 전 경기 일괄 예측 |
| GET | `/standings` | ELO 순위 |
| GET | `/predictions` | 예측 이력 |
| GET | `/accuracy` | 적중률 통계 |
| GET | `/game/{id}/lineup` | 경기 라인업 |

## Model Performance

학습: 2001~2022 (12,910경기) / 검증: 2023~2024 / 테스트: 2025

| Model | Test Accuracy | Note |
|-------|--------------|------|
| Baseline (홈팀) | 51.3% | |
| ELO | 54.4% | 가장 안정적 |
| XGBoost v3 | 59.9% | 선발투수 피처 포함 |
| Bayesian v3 | 59.6% | LightGBM+Calibration |
| Ensemble | 57.2% | 3모델 평균 |

## Multi-Agent Debate

논문 기반 설계:
- [Du et al. 2023](https://arxiv.org/abs/2305.14325) — Multi-agent debate improves reasoning
- [ReConcile (Chen et al. 2023)](https://arxiv.org/abs/2309.13007) — Diverse models > same model copies

에이전트별 역할:
| Agent | Model | Role |
|-------|-------|------|
| Analyst | GPT-4o | 통계 분석, ML 출력 해석 |
| Scout | Claude Haiku | 맥락/매치업/용병 분석 |
| Critic | GPT-4-turbo | 반론, 불확실성 지적 |
| Synthesizer | GPT-4o | 최종 종합 |

## Data Sources

- [KBO 공식 사이트](https://www.koreabaseball.com) — 경기 결과, 선발투수, 라인업
- [Kaggle KBO Datasets](https://www.kaggle.com/datasets/netsong/kbo-player-dataset-by-regular-season-1982-2025) — 선수 시즌 스탯
- 선수 스탯: 2000~2025 (타자 6,368명 / 투수 5,752명)
- 경기 데이터: 15,000+ 경기

## License

MIT
