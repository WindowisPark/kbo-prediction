# 데이터 파이프라인

## 데이터 소스

| 소스 | 데이터 | 방법 | 라이선스 |
|------|--------|------|----------|
| KBO 공식 사이트 | 경기 결과, 선발투수, 라인업 | HTTP API | 공공 정보 |
| Kaggle | 선수 시즌 스탯 (1982-2025) | CSV | CC-BY-SA-4.0 |
| 자체 수집 | 경기별 선발투수 이력 | 스크래핑 | - |

## KBO API 엔드포인트

| API | 용도 | 파라미터 |
|-----|------|----------|
| `GetKboGameDate` | 이전/현재/다음 경기일 | `leId, srId, date` |
| `GetKboGameList` | 경기 상세 (선발투수, 구장, 순위) | `leId, srId, date` |
| `GetScheduleList` | 월별 경기 목록 | `leId, srIdList, seasonId, gameMonth, teamId` |
| `GetBoxScore` | 박스스코어 (라인업, 투수) | `gameId, leId, srId, seasonId` |

## 파일 구조

```
data/
├── raw/
│   ├── kbo_games_2000_2025.csv       15,036 경기
│   ├── kbo_starters.csv               선발투수 (BoxScore)
│   ├── kbo_starters_full.csv          선발투수 (GameList)
│   ├── kbo_batting_stats_*.csv        타자 원본
│   └── kbo_pitching_stats_*.csv       투수 원본
├── processed/
│   ├── batting_2000_2025.csv          6,368행 × 39열
│   ├── pitching_2000_2025.csv         5,752행 × 42열
│   └── games_with_starters.csv        경기+선발 매칭
├── features/
│   └── game_features_v5.csv           15,026행 × 103열
├── elo_ratings.json                   최신 ELO (배치 갱신)
├── prediction_history.json            분석 이력
├── daily_results.jsonl                경기 결과 누적
└── batch.log                          배치 실행 로그
```

## 일일 배치

**파일**: `scripts/daily_batch.py`
**실행**: 매일 자정 (KST)

```
Step 1: 어제 경기 결과 수집 (GetKboGameList)
Step 2: 분석 적중 여부 업데이트
         - 무승부: is_draw=True → 적중률에서 제외
         - 중복 분석: 경기별 최신 1건만 반영
Step 3: ELO 레이팅 갱신 → elo_ratings.json
Step 4: 새 경기를 games CSV에 추가
Step 5: 적중률 요약 → batch.log
```

## 2단계 배치 예측

**파일**: `scripts/batch_predict.py`
**워크플로우**: `.github/workflows/batch-predict.yml` (매시간 UTC 00-13)

```
Phase 1: 경기 4시간 전 ±30분 — 선발투수 + 예상 라인업 기반 분석
Phase 2: 경기 1시간 전 ±30분 — 확정 라인업 반영 재분석
Fallback: 누락된 경기 자동 보충
```

결과는 `PreComputedPrediction` DB 테이블에 저장, `/predict` 요청 시 캐시로 활용.

## 초기 데이터 수집 스크립트

| 스크립트 | 용도 | 소요 |
|----------|------|------|
| `scripts/download_kaggle.py` | Kaggle CSV 다운로드 + 2000년 필터 | ~1분 |
| `scripts/collect_all.py` | KBO 경기 결과 전체 스크래핑 | ~30분 |
| `scripts/scrape_home_starters.py` | 홈 선발투수 (GameList 방식) | ~30분 |
| `backend/scrapers/kbo_starter_scraper.py` | 선발투수 (BoxScore 방식) | ~2시간 |
