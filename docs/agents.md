# 멀티 에이전트 토론 설계

**논문 기반**: Du et al. 2023, ReConcile (Chen et al. 2023)

## 토론 프로토콜

```
Phase 1: 독립 분석 ─── 3 에이전트 병렬
Phase 2: 토론 2라운드 ─ 라운드별 3 에이전트 병렬
Phase 3: 종합 ──────── Synthesizer 1회
```

Phase2 결과만 Synthesizer에 전달 (Phase1은 이미 반영됨 → 토큰 40-50% 절약)

## 에이전트 구성

| Agent | LLM | temp | 역할 |
|-------|-----|------|------|
| Analyst | GPT-4o | 0.4 | 통계 해석, ML 교차검증 |
| Scout | Claude Haiku | 0.4 | 맥락, 용병, 신인, 매치업 |
| Critic | GPT-4-turbo | 0.4 | 반론, 불확실성, Devil's Advocate |
| Synthesizer | GPT-4o | 0.1 | 최종 JSON 출력 |

## 컨텍스트 주입 체계

```
에이전트가 받는 정보:
  1. ML 모델 출력 (XGB/ELO/LGBM 확률)
  2. 팀 데이터 (ELO, 승률, OPS, ERA, 상대전적)
  3. 최근 5경기 결과 (W/L, 상대, 스코어)
  4. 시즌 성적 (승-패, 승률)
  5. 올시즌 상대전적
  6. 선발투수 상세 (ERA/FIP/WAR + 용병/신인 플래그)
  7. GPT-4o 리서치 (LLM 지식 기반 팀 동향)
  8. 구장 정보
```

## 외국인/신인 판별

**파일**: `backend/utils/player_stats.py`

| Draft 컬럼 패턴 | 판별 |
|-----------------|------|
| "자유선발" / "외국인" | `is_foreign=True` |
| 드래프트 연도 == 현재 연도 | `is_rookie=True` |
| 외국인 + 이전 KBO 기록 없음 | `is_debut_foreign=True` → "적응 불확실" |

## 안전장치

| 항목 | 구현 |
|------|------|
| API 재시도 | 3회, exponential backoff (2/4/8초) |
| 클라이언트 캐싱 | 싱글턴 패턴 `_client_cache` |
| JSON 파싱 | ```json 우선 → `{.*}` fallback → 경고 |
| 확률 추출 | 명시 패턴 우선 → generic 시 경고 로그 |
| 토큰 로깅 | 호출별 input/output 토큰 수 기록 |

## 비용 추정

| 항목 | 호출/경기 | 일 5경기 | 월 |
|------|----------|---------|-----|
| Context Gatherer | 1 | 5 | 150 |
| Phase1 | 3 | 15 | 450 |
| Phase2 (2R) | 6 | 30 | 900 |
| Synthesizer | 1 | 5 | 150 |
| **합계** | **11** | **55** | **~1,650** |
| **비용** | ~$0.36 | ~$1.8 | **~$54** |
