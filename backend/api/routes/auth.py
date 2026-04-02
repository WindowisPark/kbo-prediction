"""인증 라우터 — 회원가입, 로그인, 토큰 갱신, 이메일 인증."""
from datetime import datetime, timezone

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel, EmailStr, Field
from sqlalchemy.orm import Session

from backend.api.deps import get_db, get_current_user
from backend.auth.models import User, VerificationCode
from backend.auth.password import hash_password, verify_password, validate_password
from backend.auth.jwt_handler import create_access_token, create_refresh_token, verify_token
from backend.auth.email import generate_code, get_expiry, send_verification_email
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
    is_verified: bool = False


class RefreshRequest(BaseModel):
    refresh_token: str


class VerifyEmailRequest(BaseModel):
    code: str = Field(min_length=6, max_length=6)


class UserProfile(BaseModel):
    id: int
    email: str
    nickname: str
    tier: str
    is_verified: bool


# --- Helpers ---

INVALID_CREDENTIALS_MSG = "Invalid email or password"


def _create_and_send_code(db: Session, email: str) -> bool:
    """인증 코드 생성 → DB 저장 → 이메일 발송."""
    # 기존 미사용 코드 삭제
    db.query(VerificationCode).filter(VerificationCode.email == email).delete()
    db.flush()

    code = generate_code()
    vc = VerificationCode(email=email, code=code, expires_at=get_expiry())
    db.add(vc)
    db.commit()

    return send_verification_email(email, code)


def _make_tokens(user: User) -> TokenResponse:
    return TokenResponse(
        access_token=create_access_token(user.id, user.email, user.tier, user.is_verified),
        refresh_token=create_refresh_token(user.id),
        is_verified=user.is_verified,
    )


# --- Endpoints ---

@router.post("/register", response_model=TokenResponse, status_code=201)
def register(req: RegisterRequest, db: Session = Depends(get_db)):
    pw_error = validate_password(req.password)
    if pw_error:
        raise HTTPException(status_code=422, detail=pw_error)

    existing = db.query(User).filter(User.email == req.email).first()
    if existing:
        raise HTTPException(status_code=409, detail="Email already registered")

    user = User(
        email=req.email,
        nickname=req.nickname,
        password_hash=hash_password(req.password),
        tier="free",
        is_verified=False,
    )
    db.add(user)
    db.commit()
    db.refresh(user)

    # 인증 코드 발송
    _create_and_send_code(db, user.email)

    return _make_tokens(user)


@router.post("/login", response_model=TokenResponse)
def login(req: LoginRequest, db: Session = Depends(get_db)):
    user = db.query(User).filter(User.email == req.email).first()
    if not user or not verify_password(req.password, user.password_hash):
        raise HTTPException(status_code=401, detail=INVALID_CREDENTIALS_MSG)

    return _make_tokens(user)


@router.post("/refresh", response_model=TokenResponse)
def refresh(req: RefreshRequest, db: Session = Depends(get_db)):
    try:
        payload = verify_token(req.refresh_token, expected_type="refresh")
    except JWTError:
        raise HTTPException(status_code=401, detail="Invalid or expired refresh token")

    user = db.query(User).filter(User.id == int(payload["sub"])).first()
    if not user or not user.is_active:
        raise HTTPException(status_code=401, detail="Invalid or expired refresh token")

    return _make_tokens(user)


@router.post("/verify-email")
def verify_email(req: VerifyEmailRequest, user: User = Depends(get_current_user), db: Session = Depends(get_db)):
    """이메일 인증 코드 확인."""
    if user.is_verified:
        return {"status": "already_verified"}

    vc = db.query(VerificationCode).filter(
        VerificationCode.email == user.email,
        VerificationCode.code == req.code,
    ).first()

    if not vc:
        raise HTTPException(status_code=400, detail="잘못된 인증 코드입니다")

    if vc.expires_at.replace(tzinfo=timezone.utc) < datetime.now(timezone.utc):
        raise HTTPException(status_code=400, detail="인증 코드가 만료되었습니다. 재발송해 주세요")

    # 인증 완료
    user.is_verified = True
    db.query(VerificationCode).filter(VerificationCode.email == user.email).delete()
    db.commit()

    return {
        "status": "verified",
        "access_token": create_access_token(user.id, user.email, user.tier, True),
        "refresh_token": create_refresh_token(user.id),
    }


@router.post("/resend-code")
def resend_code(user: User = Depends(get_current_user), db: Session = Depends(get_db)):
    """인증 코드 재발송."""
    if user.is_verified:
        return {"status": "already_verified"}

    sent = _create_and_send_code(db, user.email)
    if not sent:
        raise HTTPException(status_code=500, detail="이메일 발송에 실패했습니다")

    return {"status": "sent"}


@router.get("/me", response_model=UserProfile)
def me(user: User = Depends(get_current_user)):
    return UserProfile(
        id=user.id, email=user.email, nickname=user.nickname,
        tier=user.tier, is_verified=user.is_verified,
    )
