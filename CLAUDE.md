# KBO AI Analyzer

KBO 야구 경기 분석 플랫폼 — ML 모델 + 멀티 에이전트 토론.

## 핵심 문서 (반드시 참조)

- [docs/architecture.md](docs/architecture.md) — 시스템 구조, 모듈 의존성, 동시성 모델
- [docs/models.md](docs/models.md) — ML 모델 명세 (XGBoost, ELO, EnsembleLGBM)
- [docs/features.md](docs/features.md) — 97개 피처 목록, 누수 방지 체크리스트
- [docs/agents.md](docs/agents.md) — 멀티 에이전트 토론 설계, 비용 추정
- [docs/data-pipeline.md](docs/data-pipeline.md) — 데이터 소스, 파일 구조, 일일 배치
- [docs/api-reference.md](docs/api-reference.md) — API 엔드포인트 명세
- [docs/roadmap.md](docs/roadmap.md) — 개발 로드맵 (완료/진행/예정)

## 실행

```bash
# 백엔드
python -m uvicorn backend.api.app:app --host 0.0.0.0 --port 8000

# 프론트엔드
cd frontend-app && npm run dev

# 일일 배치
python scripts/daily_batch.py
```

## 주의사항

- `.env`에 `ANTHROPIC_API_KEY`, `OPENAI_API_KEY` 필수
- 서비스 용어: "분석" 사용 ("예측" 아님) — 법적 포지셔닝
- 면책 배너 상시 노출 유지
- 데이터 누수 방지: 전년도 스탯만 사용, rolling은 shift(1)
