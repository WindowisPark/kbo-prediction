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
- [x] CORS 배포 도메인 제한 (Vercel + localhost + 프리뷰 regex)
- [x] 계정 시스템 (JWT 인증, SQLite, 보안 헤더, 81개 테스트)
- [x] 이메일 인증 (Resend API, 6자리 코드, 미인증 시 /predict 차단)
- [x] 티어별 콘텐츠 접근 제어 (API + 프론트엔드)
  - Free: 승리팀만 (확률 숨김), 요인 1줄, 1회/일
  - Basic: 확률 + 요인 3줄 + reasoning 200자, 5회/일
  - Pro: 전체 + ML 상세 + 토론 + 무제한 + 재분석
- [x] 프론트엔드 auth UI (로그인/회원가입/마이페이지/인증)
- [x] 티어별 UI (블러, 잠금, 업그레이드 CTA, 히어로 배너)
- [x] Stripe 결제 연동 (Checkout Session, Webhook, 자동 티어 변경)
- [x] 경기 전 라인업 수집 (GetLineUpAnalysis API)
- [x] 예상 라인업 추론 (최근 경기 빈도 기반)
- [x] 2단계 배치 파이프라인 (경기 시간 기준 동적 스케줄링)
  - Phase 1: 4시간 전 — 선발투수 + 예상 라인업
  - Phase 2: 1시간 전 — 확정 라인업 반영
  - Fallback: 누락 자동 보충
- [x] 최근 경기 맥락 10경기로 확장 (시즌 초 가용 수 기준)
- [x] passlib→bcrypt 직접 사용 (bcrypt>=4.1 호환)
- [x] Stripe 결제 테스트 완료 (Checkout + Webhook + 자동 tier 변경)
- [x] Resend 이메일 인증 연동 완료
- [x] PostgreSQL 전환 (Railway 재배포 시 데이터 유실 방지)
- [x] prediction_history + llm_costs DB 마이그레이션 (파일→PostgreSQL)
- [x] Standings 현재 시즌 데이터 반영 (daily_results.jsonl 기반 승률/연승)
- [x] 카드 미리보기 승자 기준 확률 표시
- [x] 예상 라인업 fallback (최근 경기 빈도 기반)
- [x] 문서 정합성 수정 (agents.md 모델 배정, features.md 버전, data-pipeline.md)
- [x] openai 의존성 추가
- [x] 배치 크래시 수정 (CSV 파일 없을 때 Step 4 스킵)

## Phase 1: 수익화 잔여

- [ ] 이용약관/개인정보처리방침 결제 관련 업데이트
- [ ] 커스텀 도메인 연결 (fullcount-ai.com) + Resend 도메인 인증
- [ ] Stripe 라이브 모드 전환 (사업자 인증 후)
- [ ] 4월 적중률 검증 (130경기+, 목표 55%+) — 병행 진행

## Phase 2: 구독 고도화 (중간 우선순위)

- [ ] 토스페이먼츠 연동 (사업자 등록 후)
- [ ] 구독 관리 (자동갱신/해지 UI)
- [ ] SSE 스트리밍 (분석 진행 실시간)
- [ ] Standings ELO 실시간 반영 (Railway 환경 호환)

## Phase 3: 성장 (낮은 우선순위)

- [ ] 쿠폰/프로모션 시스템
- [ ] 카카오 알림톡 연동
- [ ] 웹 검색 API 연동 (Tavily/SerpAPI)
- [ ] PostgreSQL 전환 (사용자 증가 시)
- [ ] WebSocket 실시간 스코어
- [ ] 날씨/기온 피처
- [ ] 연속 경기/이동거리 피처
- [ ] NGBoost (진짜 Bayesian)
- [ ] MLB / NPB 확장
- [ ] B2B API
