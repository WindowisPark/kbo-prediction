"""SQLAlchemy 데이터베이스 설정 — SQLite (개발) / PostgreSQL (프로덕션)."""
import os
from contextlib import asynccontextmanager, contextmanager

from sqlalchemy import create_engine
from sqlalchemy.orm import DeclarativeBase, Session, sessionmaker

DATABASE_URL = os.getenv("DATABASE_URL", "sqlite:///./data/kbo_auth.db")

# SQLite 호환
if DATABASE_URL.startswith("sqlite"):
    engine = create_engine(DATABASE_URL, connect_args={"check_same_thread": False})
else:
    engine = create_engine(DATABASE_URL)

SessionLocal = sessionmaker(bind=engine, autocommit=False, autoflush=False)


class Base(DeclarativeBase):
    pass


def get_db():
    """FastAPI Depends용 DB 세션 제너레이터."""
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()


@contextmanager
def get_db_session():
    """동기 컨텍스트 매니저 — 테스트/스크립트용."""
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()


def init_db():
    """테이블 생성 (개발용, 프로덕션은 Alembic 사용)."""
    from backend.auth.models import User  # noqa: F401
    Base.metadata.create_all(bind=engine)
