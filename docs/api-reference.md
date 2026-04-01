# API Reference

Base URL: `http://localhost:8000`

## 엔드포인트

### GET /
헬스체크
```json
{"status": "ok", "models_loaded": true, "prediction_count": 5}
```

### GET /today?date={YYYYMMDD}
경기 일정. date 미지정 시 가장 가까운 경기일.
```json
{
  "game_date": "20260401",
  "game_date_text": "2026.04.01",
  "prev_date": "20260331",
  "next_date": "20260402",
  "games": [{
    "game_id": "20260401HTLG0",
    "date": "2026-04-01",
    "time": "18:30",
    "away_team": "KIA",
    "home_team": "LG",
    "away_score": null,
    "home_score": null,
    "status": "scheduled",
    "stadium": "잠실",
    "away_starter": "올러",
    "home_starter": "톨허스트",
    "away_rank": 7,
    "home_rank": 5,
    "lineup_available": false,
    "tv": "KN-T"
  }]
}
```

### POST /predict
단일 경기 분석. async 처리 (동시 요청 가능).

Request:
```json
{
  "home_team": "LG",
  "away_team": "KIA",
  "date": "2026-04-01",
  "extra_context": "",
  "home_starter": "톨허스트",
  "away_starter": "올러"
}
```

Response:
```json
{
  "home_team": "LG",
  "away_team": "KIA",
  "date": "2026-04-01",
  "predicted_winner": "KIA",
  "home_win_probability": 0.47,
  "confidence": "medium",
  "key_factors": ["선발투수 차이", "최근 폼"],
  "reasoning": "...",
  "model_probabilities": {
    "xgboost": 0.50,
    "elo": 0.53,
    "bayesian": 0.50
  },
  "debate_log": [{
    "agent": "Analyst",
    "model": "openai/gpt-4o",
    "round": 0,
    "probability": 0.48,
    "confidence": "medium",
    "content": "..."
  }]
}
```

### POST /today/predict
당일 전 경기 일괄 분석. asyncio.gather로 병렬 처리.

### GET /standings
ELO 순위.
```json
{
  "season": 2026,
  "teams": [
    {"team": "SSG", "elo": 1532.0, "recent_win_pct": 0.7, "streak": 4}
  ]
}
```

### GET /predictions?limit=50
분석 이력.

### GET /accuracy
적중률 (무승부 제외, 경기별 중복 제거).
```json
{
  "total_predictions": 10,
  "correct": 7,
  "accuracy": 0.7,
  "by_confidence": {
    "medium": {"total": 8, "correct": 6, "accuracy": 0.75}
  }
}
```

### GET /game/{game_id}/lineup
경기 라인업 (종료 후만 데이터 있음).

### GET /teams
현재 KBO 팀 목록.
