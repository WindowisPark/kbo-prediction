# 개발 로드맵

## 완료

- [x] 데이터 수집 파이프라인 (KBO 스크래핑 + Kaggle)
- [x] 피처 엔지니어링 v4 (104 피처, 양쪽 선발투수)
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

## 높은 우선순위

- [x] 실시간 시즌 누적 스탯 반영 (에이전트 맥락 주입 방식)
- [ ] 배포 (Vercel + Railway)
- [ ] API 인증 + Rate Limiting
- [ ] CORS 도메인 제한

## 중간 우선순위

- [ ] 경기 전 라인업 수집 (Playwright)
- [ ] Redis 캐싱

## 낮은 우선순위

- [ ] MLB / NPB 확장
- [ ] WebSocket 실시간 스코어
- [ ] PostgreSQL 전환
- [ ] 날씨/기온 피처
- [ ] 연속 경기/이동거리 피처
- [ ] SSE 스트리밍 (분석 진행 실시간)
- [ ] NGBoost (진짜 Bayesian)
- [ ] 웹 검색 API 연동 (Tavily/SerpAPI)
