"""
Shared fixtures for KBO security tests.

Provides:
  - async_client: httpx.AsyncClient wired to the FastAPI app via ASGITransport
  - auth helpers: register_user, login_user, get_auth_headers
  - per-tier user fixtures: free_token, basic_token, pro_token
"""
import os
# 테스트용 SQLite (PostgreSQL 대신)
os.environ["DATABASE_URL"] = "sqlite:///./data/test_auth.db"
os.environ["JWT_SECRET_KEY"] = "test-secret-key-for-testing-only"

import pytest
import pytest_asyncio
import httpx
from httpx import ASGITransport

from backend.auth.database import Base, engine

# 테스트 시작 전 테이블 생성, 종료 후 정리
@pytest.fixture(autouse=True, scope="session")
def setup_test_db():
    from backend.auth.models import User  # noqa: F401
    Base.metadata.create_all(bind=engine)
    yield
    Base.metadata.drop_all(bind=engine)

@pytest.fixture(autouse=True)
def clean_tables():
    """각 테스트 후 users 테이블 + rate limiter 초기화."""
    yield
    from backend.auth.models import User
    with engine.connect() as conn:
        conn.execute(User.__table__.delete())
        conn.commit()
    # Rate limiter 카운터 초기화
    from backend.api.middleware.rate_limiter import reset_counters
    reset_counters()

from backend.api.app import app


# ---------------------------------------------------------------------------
# Core async client
# ---------------------------------------------------------------------------

@pytest_asyncio.fixture
async def async_client():
    """Yield an httpx AsyncClient bound to the FastAPI app."""
    transport = ASGITransport(app=app)
    async with httpx.AsyncClient(transport=transport, base_url="http://test") as client:
        yield client


# ---------------------------------------------------------------------------
# Auth helpers
# ---------------------------------------------------------------------------

async def register_user(
    client: httpx.AsyncClient,
    email: str,
    password: str,
    nickname: str = "tester",
) -> httpx.Response:
    """Register a new user and return the raw response."""
    return await client.post(
        "/auth/register",
        json={"email": email, "password": password, "nickname": nickname},
    )


async def login_user(
    client: httpx.AsyncClient,
    email: str,
    password: str,
) -> httpx.Response:
    """Login and return the raw response."""
    return await client.post(
        "/auth/login",
        json={"email": email, "password": password},
    )


async def get_auth_headers(
    client: httpx.AsyncClient,
    email: str,
    password: str,
    nickname: str = "tester",
) -> dict[str, str]:
    """Register (if needed) + login, return Authorization header dict."""
    await register_user(client, email, password, nickname)
    resp = await login_user(client, email, password)
    data = resp.json()
    return {"Authorization": f"Bearer {data['access_token']}"}


# ---------------------------------------------------------------------------
# Per-tier token fixtures
# ---------------------------------------------------------------------------

@pytest_asyncio.fixture
async def free_token(async_client: httpx.AsyncClient) -> dict[str, str]:
    """Auth headers for a Free-tier user."""
    return await get_auth_headers(
        async_client,
        email="free@test.com",
        password="Test1234!",
        nickname="free_user",
    )


@pytest_asyncio.fixture
async def basic_token(async_client: httpx.AsyncClient) -> dict[str, str]:
    """Auth headers for a Basic-tier user.

    Assumes POST /admin/set-tier or a test seeding mechanism exists.
    The test registers the user, then upgrades tier via internal endpoint.
    """
    headers = await get_auth_headers(
        async_client,
        email="basic@test.com",
        password="Test1234!",
        nickname="basic_user",
    )
    # Upgrade tier — the implementation should expose an internal/admin
    # endpoint or the tests should seed the DB directly.  For now we call
    # the expected admin endpoint.
    await async_client.post(
        "/admin/set-tier",
        json={"email": "basic@test.com", "tier": "basic"},
        headers=headers,  # may need admin creds; adjust once impl exists
    )
    # Re-login to get token with updated tier claim
    resp = await login_user(async_client, "basic@test.com", "Test1234!")
    data = resp.json()
    return {"Authorization": f"Bearer {data['access_token']}"}


@pytest_asyncio.fixture
async def pro_token(async_client: httpx.AsyncClient) -> dict[str, str]:
    """Auth headers for a Pro-tier user."""
    headers = await get_auth_headers(
        async_client,
        email="pro@test.com",
        password="Test1234!",
        nickname="pro_user",
    )
    await async_client.post(
        "/admin/set-tier",
        json={"email": "pro@test.com", "tier": "pro"},
        headers=headers,
    )
    resp = await login_user(async_client, "pro@test.com", "Test1234!")
    data = resp.json()
    return {"Authorization": f"Bearer {data['access_token']}"}
