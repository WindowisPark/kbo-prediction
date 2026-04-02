"""
CORS Security Tests
====================
Verify that the API only accepts requests from authorized origins.

Security properties under test:
  - Wildcard origin ("*") is NOT reflected back.
  - Only the Vercel production domain and localhost:3000 are allowed.
  - Preflight (OPTIONS) returns correct Access-Control-* headers for
    allowed origins and omits them for disallowed origins.
  - Access-Control-Allow-Credentials is "true" for allowed origins.

All tests are expected to FAIL against the current implementation
(allow_origins=["*"]) and PASS once CORS is locked down.
"""
import pytest
import httpx
from httpx import ASGITransport

from backend.api.app import app

ALLOWED_ORIGINS = [
    "https://kbo-prediction-lilac.vercel.app",
    "http://localhost:3000",
]

DISALLOWED_ORIGINS = [
    "https://evil.com",
    "https://kbo-prediction-lilac.vercel.app.evil.com",
    "http://localhost:9999",
    "null",
]


@pytest.fixture
def transport():
    return ASGITransport(app=app)


# ---------------------------------------------------------------------------
# Allowed origins
# ---------------------------------------------------------------------------

@pytest.mark.asyncio
@pytest.mark.parametrize("origin", ALLOWED_ORIGINS)
async def test_allowed_origin_gets_cors_headers(transport, origin: str):
    """Requests from allowed origins must receive matching ACAO header."""
    async with httpx.AsyncClient(transport=transport, base_url="http://test") as c:
        resp = await c.get("/", headers={"Origin": origin})

    assert resp.headers.get("access-control-allow-origin") == origin


@pytest.mark.asyncio
@pytest.mark.parametrize("origin", ALLOWED_ORIGINS)
async def test_allowed_origin_credentials_header(transport, origin: str):
    """Allowed origins must receive Access-Control-Allow-Credentials: true."""
    async with httpx.AsyncClient(transport=transport, base_url="http://test") as c:
        resp = await c.get("/", headers={"Origin": origin})

    assert resp.headers.get("access-control-allow-credentials") == "true"


@pytest.mark.asyncio
@pytest.mark.parametrize("origin", ALLOWED_ORIGINS)
async def test_preflight_returns_correct_headers(transport, origin: str):
    """OPTIONS preflight for allowed origin returns 200 with CORS headers."""
    async with httpx.AsyncClient(transport=transport, base_url="http://test") as c:
        resp = await c.options(
            "/predict",
            headers={
                "Origin": origin,
                "Access-Control-Request-Method": "POST",
                "Access-Control-Request-Headers": "Content-Type, Authorization",
            },
        )

    assert resp.status_code == 200
    assert resp.headers.get("access-control-allow-origin") == origin
    allow_headers = resp.headers.get("access-control-allow-headers", "").lower()
    assert "authorization" in allow_headers
    assert "content-type" in allow_headers


# ---------------------------------------------------------------------------
# Disallowed / wildcard origins
# ---------------------------------------------------------------------------

@pytest.mark.asyncio
async def test_wildcard_origin_not_reflected(transport):
    """The server must NOT echo back '*' as the allowed origin.

    When credentials are enabled, reflecting '*' is a browser-level error
    and a security misconfiguration.
    """
    async with httpx.AsyncClient(transport=transport, base_url="http://test") as c:
        resp = await c.get("/", headers={"Origin": "https://evil.com"})

    acao = resp.headers.get("access-control-allow-origin")
    assert acao != "*", "Wildcard ACAO is a security misconfiguration"


@pytest.mark.asyncio
@pytest.mark.parametrize("origin", DISALLOWED_ORIGINS)
async def test_disallowed_origin_gets_no_cors_headers(transport, origin: str):
    """Requests from unknown origins must NOT receive ACAO header."""
    async with httpx.AsyncClient(transport=transport, base_url="http://test") as c:
        resp = await c.get("/", headers={"Origin": origin})

    acao = resp.headers.get("access-control-allow-origin")
    assert acao is None or acao not in ("*", origin), (
        f"Disallowed origin '{origin}' should not receive ACAO header, got: {acao}"
    )


@pytest.mark.asyncio
@pytest.mark.parametrize("origin", DISALLOWED_ORIGINS)
async def test_disallowed_preflight_rejected(transport, origin: str):
    """Preflight from disallowed origin must not include ACAO header."""
    async with httpx.AsyncClient(transport=transport, base_url="http://test") as c:
        resp = await c.options(
            "/predict",
            headers={
                "Origin": origin,
                "Access-Control-Request-Method": "POST",
                "Access-Control-Request-Headers": "Content-Type",
            },
        )

    acao = resp.headers.get("access-control-allow-origin")
    assert acao is None or acao not in ("*", origin), (
        f"Preflight for disallowed origin '{origin}' should be rejected"
    )


@pytest.mark.asyncio
async def test_no_origin_header_still_works(transport):
    """Requests with no Origin header (e.g., curl) should succeed normally."""
    async with httpx.AsyncClient(transport=transport, base_url="http://test") as c:
        resp = await c.get("/")

    assert resp.status_code == 200
