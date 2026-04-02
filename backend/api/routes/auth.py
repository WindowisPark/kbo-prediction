"""인증 라우터 — 회원가입, 로그인, 토큰 갱신."""
from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel, EmailStr, Field
from sqlalchemy.orm import Session

from backend.api.deps import get_db, get_current_user
from backend.auth.models import User
from backend.auth.password import hash_password, verify_password, validate_password
from backend.auth.jwt_handler import create_access_token, create_refresh_token, verify_token
from jose import JWTError

router = APIRouter(prefix="/auth", tags=["auth"])


# --- Schemas ---

class RegisterRequest(BaseModel):
    email: EmailStr
    password: str = Field(min_length=1, max_length=128)
    nickname: str = Field(default="user", min_length=1, max_length=100)


class LoginRequest(BaseModel):
    email: str
    password: str


class TokenResponse(BaseModel):
    access_token: str
    refresh_token: str
    token_type: str = "bearer"


class RefreshRequest(BaseModel):
    refresh_token: str


class UserProfile(BaseModel):
    id: int
    email: str
    nickname: str
    tier: str


# --- Endpoints ---

INVALID_CREDENTIALS_MSG = "Invalid email or password"


@router.post("/register", response_model=TokenResponse, status_code=201)
def register(req: RegisterRequest, db: Session = Depends(get_db)):
    # 비밀번호 정책 검증
    pw_error = validate_password(req.password)
    if pw_error:
        raise HTTPException(status_code=422, detail=pw_error)

    # 이메일 중복 확인
    existing = db.query(User).filter(User.email == req.email).first()
    if existing:
        raise HTTPException(status_code=409, detail="Email already registered")

    user = User(
        email=req.email,
        nickname=req.nickname,
        password_hash=hash_password(req.password),
        tier="free",
    )
    db.add(user)
    db.commit()
    db.refresh(user)

    return TokenResponse(
        access_token=create_access_token(user.id, user.email, user.tier),
        refresh_token=create_refresh_token(user.id),
    )


@router.post("/login", response_model=TokenResponse)
def login(req: LoginRequest, db: Session = Depends(get_db)):
    user = db.query(User).filter(User.email == req.email).first()
    if not user or not verify_password(req.password, user.password_hash):
        raise HTTPException(status_code=401, detail=INVALID_CREDENTIALS_MSG)

    return TokenResponse(
        access_token=create_access_token(user.id, user.email, user.tier),
        refresh_token=create_refresh_token(user.id),
    )


@router.post("/refresh", response_model=TokenResponse)
def refresh(req: RefreshRequest, db: Session = Depends(get_db)):
    try:
        payload = verify_token(req.refresh_token, expected_type="refresh")
    except JWTError:
        raise HTTPException(status_code=401, detail="Invalid or expired refresh token")

    user = db.query(User).filter(User.id == int(payload["sub"])).first()
    if not user or not user.is_active:
        raise HTTPException(status_code=401, detail="Invalid or expired refresh token")

    return TokenResponse(
        access_token=create_access_token(user.id, user.email, user.tier),
        refresh_token=create_refresh_token(user.id),
    )


@router.get("/me", response_model=UserProfile)
def me(user: User = Depends(get_current_user)):
    return UserProfile(id=user.id, email=user.email, nickname=user.nickname, tier=user.tier)
