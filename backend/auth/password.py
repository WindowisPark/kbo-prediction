"""bcrypt 비밀번호 해싱."""
import re

from passlib.context import CryptContext

pwd_context = CryptContext(schemes=["bcrypt"], deprecated="auto")


def hash_password(password: str) -> str:
    return pwd_context.hash(password)


def verify_password(plain: str, hashed: str) -> bool:
    return pwd_context.verify(plain, hashed)


def validate_password(password: str) -> str | None:
    """비밀번호 정책 검증. 위반 시 에러 메시지 반환, 통과 시 None."""
    if len(password) < 8:
        return "Password must be at least 8 characters"
    if not re.search(r"[a-zA-Z]", password):
        return "Password must contain at least one letter"
    if not re.search(r"\d", password):
        return "Password must contain at least one number"
    return None
