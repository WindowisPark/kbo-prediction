# 개발 로드맵

## 완료

- [x] 데이터 수집 파이프라인 (KBO 스크래핑 + Kaggle)
- [x] 피처 엔지니어링 v5 (103 피처, 양쪽 선발투수, 올시즌 스탯)
- [x] ML 모델 3종 (XGBoost 62.9%, ELO 54.6%, EnsembleLGBM 62.0%)
- [x] Stacking 앙상블 (LogisticRegression 메타 러너: 61.6%)
- [x] 멀티 에이전트 토론 (3-provider: Gemini+GPT+Claude)
- [x] 자동 맥락 수집 (최근 경기, 선발투수 스탯, 용병/신인 판별)
- [x] FastAPI 백엔드 (async 병렬, 5경기 동시)
- [x] Next.js 프론트엔드 (대시보드, 날짜 네비, 엠블럼)
- [x] 일일 배치 (ELO 갱신, 적중률 추적)
- [x] 법적 준수 (면책/약관/개인정보, "분석" 포지셔닝)
- [x] 전문가 리뷰 반영 (LLM 서빙 + ML 방법론)
- [x] 홈 선발투수 개인 스탯 피처 (v4: +2%p)
- [x] Optuna 하이퍼파라미터 자동 튜닝 (XGB 62.9%)
- [x] Calibration 검증 (predicted-actual gap < 3%)
- [x] 홈 어드밴티지 최적값 (KBO 실측: 30→20)
- [x] 모델 버전 관리 (joblib save/load)
- [x] LLM 비용 대시보드 (/costs API + cost_tracker)
- [x] 실시간 시즌 누적 스탯 반영 (에이전트 맥락 주입 방식)
- [x] 캐싱 (Redis + 파일 fallback, 4시간 TTL)
- [x] 배포 완료
  - Frontend: kbo-prediction-lilac.vercel.app (Vercel)
  - Backend: kbo-prediction-production.up.railway.app (Railway)
  - Daily Batch: GitHub Actions (KST 00:00 cron)

## Phase 1: 수익화 기반 (높은 우선순위)

- [x] CORS 배포 도메인만 허용 (Vercel + localhost:3000)
- [x] 계정 시스템
  - JWT 인증 (회원가입/로그인/토큰 갱신)
  - 사용자 DB (SQLite → 추후 PostgreSQL 전환)
  - per-user Rate Limiting (Free 10/hr, Basic 50/hr, Pro 200/hr)
  - 보안 헤더 미들웨어 (CSP, HSTS, X-Frame-Options 등)
  - 보안 테스트 67개 전체 통과
- [x] 프리미엄 콘텐츠 접근 제어 (API 레벨)
  - Free / Basic / Pro 티어별 응답 필터링
- [ ] 구독 + 결제 MVP (monetization.md Phase 1)
  - 토스페이먼츠 단건 월간 결제
  - 이용약관/개인정보처리방침 업데이트
- [ ] 4월 적중률 검증 (130경기+, 목표 55%+) — 병행 진행

## Phase 2: 구독 고도화 (중간 우선순위)

- [ ] 정기결제 (빌링키 + 자동갱신/해지 UI) (monetization.md Phase 2)
- [ ] 구독 관리 대시보드 (마이페이지)
- [ ] 경기 전 라인업 수집 (KBO 사이트 구조상 제한 — ASP.NET UpdatePanel)
- [ ] SSE 스트리밍 (분석 진행 실시간)

## Phase 3: 성장 (낮은 우선순위)

- [ ] 쿠폰/프로모션 시스템 (monetization.md Phase 3)
- [ ] 카카오 알림톡 연동
- [ ] 웹 검색 API 연동 (Tavily/SerpAPI)
- [ ] PostgreSQL 전환 (사용자 증가 시)
- [ ] WebSocket 실시간 스코어
- [ ] 날씨/기온 피처
- [ ] 연속 경기/이동거리 피처
- [ ] NGBoost (진짜 Bayesian)
- [ ] MLB / NPB 확장
- [ ] B2B API
