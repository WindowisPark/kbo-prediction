"""
예측 결과 캐싱 — 같은 매치업 중복 LLM 호출 방지.

Redis 사용 가능하면 Redis, 아니면 파일 기반 TTL 캐시.
캐시 키: {date}_{home}_{away}
TTL: 4시간 (선발투수 변경 등 반영)
"""
import json
import hashlib
import logging
import time
from pathlib import Path

logger = logging.getLogger(__name__)
ROOT = Path(__file__).parent.parent.parent
CACHE_DIR = ROOT / "data" / "cache"
CACHE_DIR.mkdir(parents=True, exist_ok=True)
CACHE_TTL = 4 * 3600  # 4시간

_redis_client = None


def _get_redis():
    global _redis_client
    if _redis_client is None:
        try:
            import redis
            import os
            url = os.getenv("REDIS_URL", "redis://localhost:6379")
            _redis_client = redis.from_url(url, decode_responses=True)
            _redis_client.ping()
            logger.info("Redis connected")
        except Exception:
            _redis_client = False  # Redis 없음 표시
    return _redis_client if _redis_client else None


def _cache_key(date: str, home_team: str, away_team: str) -> str:
    return f"pred:{date}:{home_team}:{away_team}"


def get_cached(date: str, home_team: str, away_team: str) -> dict | None:
    """캐시된 예측 결과 조회."""
    key = _cache_key(date, home_team, away_team)

    # Redis 시도
    r = _get_redis()
    if r:
        try:
            data = r.get(key)
            if data:
                logger.debug(f"Cache HIT (redis): {key}")
                return json.loads(data)
        except Exception:
            pass

    # 파일 캐시 fallback
    cache_file = CACHE_DIR / f"{hashlib.md5(key.encode()).hexdigest()}.json"
    if cache_file.exists():
        try:
            data = json.loads(cache_file.read_text(encoding="utf-8"))
            if time.time() - data.get("_cached_at", 0) < CACHE_TTL:
                logger.debug(f"Cache HIT (file): {key}")
                return data.get("result")
            else:
                cache_file.unlink()  # TTL 만료
        except (json.JSONDecodeError, KeyError):
            pass

    return None


def set_cached(date: str, home_team: str, away_team: str, result: dict):
    """예측 결과를 캐시에 저장."""
    key = _cache_key(date, home_team, away_team)

    # Redis 시도
    r = _get_redis()
    if r:
        try:
            r.setex(key, CACHE_TTL, json.dumps(result, ensure_ascii=False))
            logger.debug(f"Cache SET (redis): {key}")
            return
        except Exception:
            pass

    # 파일 캐시 fallback
    cache_file = CACHE_DIR / f"{hashlib.md5(key.encode()).hexdigest()}.json"
    cache_file.write_text(
        json.dumps({"_cached_at": time.time(), "result": result}, ensure_ascii=False),
        encoding="utf-8",
    )
    logger.debug(f"Cache SET (file): {key}")


def clear_cache():
    """전체 캐시 초기화."""
    # 파일 캐시
    for f in CACHE_DIR.glob("*.json"):
        f.unlink()

    # Redis
    r = _get_redis()
    if r:
        try:
            keys = r.keys("pred:*")
            if keys:
                r.delete(*keys)
        except Exception:
            pass

    logger.info("Cache cleared")
