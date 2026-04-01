# 시스템 아키텍처

## 전체 구조

```
┌─────────────────────────────────────┐
│      Presentation (Next.js 16)      │
│  Dashboard / Standings / History    │
├─────────────────────────────────────┤
│           API (FastAPI)             │
│  async + ThreadPoolExecutor(5)      │
├──────────┬──────────┬───────────────┤
│  ML      │ Context  │  Agent        │
│  Models  │ Gather   │  Debate       │
├──────────┴──────────┴───────────────┤
│         Data (CSV / JSON)           │
└─────────────────────────────────────┘
```

## 모듈 의존성

```
app.py
  ├── predictor.py
  │     ├── xgboost_model.py
  │     ├── elo_model.py
  │     ├── bayesian_model.py (EnsembleLGBM)
  │     ├── context_gatherer.py
  │     │     ├── player_stats.py
  │     │     └── llm_clients.py
  │     └── debate.py
  │           ├── llm_clients.py
  │           └── prompts.py
  ├── kbo_today.py
  ├── kbo_lineup.py
  └── team_mapping.py
```

## 외부 의존성

| 서비스 | 용도 | 프로토콜 |
|--------|------|----------|
| KBO 공식 사이트 | 경기/선발투수/라인업 | HTTP POST (ASMX) |
| OpenAI API | GPT-4o, GPT-4-turbo | HTTPS REST |
| Anthropic API | Claude Haiku | HTTPS REST |
| Kaggle | 선수 통계 데이터셋 | CLI |

## 동시성 모델

```
/predict       → run_in_executor (1건)
/today/predict → asyncio.gather × N경기 (병렬)
Phase1/2 내부  → ThreadPoolExecutor(3) (3 에이전트 병렬)
```
