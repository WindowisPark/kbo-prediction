# API Reference

Base URL: `http://localhost:8000` (로컬) / `https://kbo-prediction-production.up.railway.app` (프로덕션)

## 인증

JWT Bearer 토큰 방식. `Authorization: Bearer {access_token}` 헤더 필요.
미인증 요청은 Free 티어 취급.

## 엔드포인트

### GET /
헬스체크
```json
{"status": "ok", "models_loaded": true, "prediction_count": 5}
```

### POST /auth/register
회원가입. 인증 코드 이메일 발송.
```json
// Request
{"email": "user@example.com", "password": "Secure123!", "nickname": "user"}
// Response (201)
{"access_token": "...", "refresh_token": "...", "token_type": "bearer", "is_verified": false}
```

### POST /auth/login
로그인.
```json
// Request
{"email": "user@example.com", "password": "Secure123!"}
// Response (200)
{"access_token": "...", "refresh_token": "...", "token_type": "bearer", "is_verified": true}
```

### POST /auth/refresh
토큰 갱신.
```json
// Request
{"refresh_token": "..."}
```

### POST /auth/verify-email
이메일 인증 코드 확인. (인증 필요)
```json
// Request
{"code": "123456"}
// Response
{"status": "verified", "access_token": "...", "refresh_token": "..."}
```

### POST /auth/resend-code
인증 코드 재발송. (인증 필요)

### GET /auth/me
내 정보. (인증 필요)
```json
{"id": 1, "email": "user@example.com", "nickname": "user", "tier": "free", "is_verified": true}
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
    "status": "scheduled",
    "stadium": "잠실",
    "away_starter": "올러",
    "home_starter": "톨허스트",
    "lineup_available": false
  }]
}
```

### POST /predict
단일 경기 분석. 배치 결과 → 캐시 → 실시간 LLM 순서로 반환.

Request:
```json
{
  "home_team": "LG",
  "away_team": "KIA",
  "date": "2026-04-01",
  "extra_context": "",
  "home_starter": "톨허스트",
  "away_starter": "올러",
  "reanalyze": false
}
```

Response (티어에 따라 필터링):
```json
{
  "home_team": "LG",
  "away_team": "KIA",
  "date": "2026-04-01",
  "predicted_winner": "KIA",
  "home_win_probability": 0.47,      // Free: null
  "confidence": "medium",
  "key_factors": ["선발투수 차이"],    // Free: 1줄, Basic: 3줄, Pro: 전체
  "reasoning": "...",                  // Free: null, Basic: 200자, Pro: 전체
  "model_probabilities": {...},        // Pro only
  "debate_log": [...],                 // Pro only
  "tier": "free"
}
```

제한: Free 1회/일, Basic 5회/일, Pro 무제한.
`reanalyze: true`는 Pro 전용 (403).
미인증 사용자는 403 (`email_not_verified`).

### POST /predict/batch
복수 경기 분석.

### POST /today/predict
당일 전 경기 일괄 분석.

### GET /standings
ELO 순위.
```json
{
  "season": 2026,
  "teams": [
    {"team": "KT", "elo": 1541.0, "recent_win_pct": 0.7, "streak": 4}
  ]
}
```

### GET /predictions?limit=50
분석 이력.

### GET /accuracy
적중률 (무승부 제외, 경기별 중복 제거). 티어별 필터링:
- Free: 전체 숫자만 (by_confidence 비어있음)
- Basic: 7일 상세
- Pro: 전체 상세

### GET /game/{game_id}/lineup
경기 라인업. 3단계 fallback: 확정 라인업 → 박스스코어 → 예상 라인업 (최근 경기 빈도 기반).
```json
{
  "game_id": "20260401HTLG0",
  "available": true,
  "source": "pregame|boxscore|expected",
  "home_lineup": [{"order": "1", "position": "우익수", "name": "홍창기"}],
  "away_lineup": [...],
  "games_used": 5  // source=expected일 때만
}
```

### GET /teams
현재 KBO 팀 목록.

### GET /costs?date={YYYY-MM-DD}
LLM API 비용 조회 (PostgreSQL 기반).

### POST /payments/create-checkout
Stripe Checkout Session 생성. (인증 필요)
```json
// Request
{"tier": "basic"}
// Response
{"checkout_url": "https://checkout.stripe.com/..."}
```

### POST /payments/webhook
Stripe Webhook. 결제 완료 시 자동 티어 업그레이드.

### POST /admin/set-tier
관리자 티어 변경 (내부/테스트용).
```json
{"email": "user@example.com", "tier": "pro"}
```
