"""FastAPI 의존성 — 인증, DB 세션, 티어 확인."""
from typing import Generator

from fastapi import Depends, HTTPException, Header
from sqlalchemy.orm import Session

from backend.auth.database import SessionLocal
from backend.auth.models import User
from backend.auth.jwt_handler import verify_token
from jose import JWTError


def get_db() -> Generator[Session, None, None]:
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()


def get_current_user_optional(
    authorization: str | None = Header(None),
    db: Session = Depends(get_db),
) -> User | None:
    """Bearer 토큰에서 사용자 추출. 토큰 없으면 None, 잘못된 토큰이면 401."""
    if not authorization or not authorization.startswith("Bearer "):
        return None

    token = authorization[7:]
    try:
        payload = verify_token(token, expected_type="access")
    except JWTError:
        raise HTTPException(status_code=401, detail="Invalid or expired token")

    user = db.query(User).filter(User.id == int(payload["sub"])).first()
    if not user or not user.is_active:
        raise HTTPException(status_code=401, detail="Invalid or expired token")
    return user


def get_current_user(
    user: User | None = Depends(get_current_user_optional),
) -> User:
    if user is None:
        raise HTTPException(status_code=401, detail="Not authenticated")
    return user


def get_user_tier(user: User | None = Depends(get_current_user_optional)) -> str:
    """티어 반환. 미인증 사용자는 'free'."""
    return user.tier if user else "free"
