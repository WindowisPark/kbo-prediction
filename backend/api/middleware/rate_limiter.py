"""분석 횟수 제한 미들웨어 — /predict 엔드포인트만 일일 횟수 제한.

티어별 일일 분석 횟수:
  Free:  1회/일
  Basic: 5회/일
  Pro:   무제한

조회 API (standings, today, teams 등)는 제한 없음.
"""
import os
import time
from collections import defaultdict

from starlette.middleware.base import BaseHTTPMiddleware
from starlette.requests import Request
from starlette.responses import JSONResponse

from backend.auth.jwt_handler import verify_token
from jose import JWTError

# 일일 분석 횟수 제한
PREDICT_DAILY_LIMITS = {
    "free": int(os.getenv("PREDICT_LIMIT_FREE", "1")),
    "basic": int(os.getenv("PREDICT_LIMIT_BASIC", "5")),
    "pro": int(os.getenv("PREDICT_LIMIT_PRO", "999999")),  # 사실상 무제한
}

DAY_SECONDS = 86400

# 분석 횟수 제한 대상 경로
PREDICT_PATHS = {"/predict", "/predict/batch", "/today/predict"}

# 저장소: {identity: {"timestamps": [t1, t2, ...], "day_start": float}}
_predict_counters: dict[str, dict] = defaultdict(lambda: {"timestamps": [], "day_start": 0.0})


def _get_identity_tier_verified(request: Request) -> tuple[str, str, bool]:
    """요청에서 사용자 ID, 티어, 인증 여부를 추출."""
    identity = request.client.host if request.client else "unknown"
    tier = "free"
    is_verified = False

    auth_header = request.headers.get("authorization", "")
    if auth_header.startswith("Bearer "):
        token = auth_header[7:]
        try:
            payload = verify_token(token, expected_type="access")
            identity = f"user:{payload['sub']}"
            tier = payload.get("tier", "free")
            is_verified = payload.get("is_verified", False)
        except JWTError:
            pass

    return identity, tier, is_verified


def reset_counters():
    """테스트용 — 카운터 초기화."""
    _predict_counters.clear()


class RateLimiterMiddleware(BaseHTTPMiddleware):
    async def dispatch(self, request: Request, call_next):
        path = request.url.path

        # 분석 엔드포인트가 아니면 제한 없이 통과
        if path not in PREDICT_PATHS or request.method != "POST":
            return await call_next(request)

        identity, tier, is_verified = _get_identity_tier_verified(request)

        # 미인증 사용자 분석 차단
        if identity.startswith("user:") and not is_verified:
            return JSONResponse(
                status_code=403,
                content={"detail": "이메일 인증이 필요합니다", "code": "email_not_verified"},
            )
        limit = PREDICT_DAILY_LIMITS.get(tier, PREDICT_DAILY_LIMITS["free"])

        now = time.time()
        counter = _predict_counters[identity]

        # 일일 리셋 (자정 기준)
        if now - counter["day_start"] >= DAY_SECONDS:
            counter["timestamps"] = []
            counter["day_start"] = now

        used = len(counter["timestamps"])

        if used >= limit:
            retry_after = int(DAY_SECONDS - (now - counter["day_start"])) + 1
            return JSONResponse(
                status_code=429,
                content={
                    "detail": "Daily prediction limit exceeded",
                    "limit": limit,
                    "used": used,
                    "tier": tier,
                },
                headers={
                    "Retry-After": str(retry_after),
                    "X-Predict-Limit": str(limit),
                    "X-Predict-Remaining": "0",
                },
            )

        counter["timestamps"].append(now)
        response = await call_next(request)
        response.headers["X-Predict-Limit"] = str(limit)
        response.headers["X-Predict-Remaining"] = str(limit - len(counter["timestamps"]))
        return response
