"""
Security Headers Tests
========================
Verify that the API sets standard security headers on every response.

Security properties under test:
  - X-Content-Type-Options: nosniff   (prevents MIME-type sniffing)
  - X-Frame-Options: DENY             (prevents clickjacking)
  - Strict-Transport-Security         (enforces HTTPS)
  - Content-Security-Policy           (restricts resource loading)

All tests are expected to FAIL until security header middleware is added.
"""
import pytest
import httpx
from httpx import ASGITransport

from backend.api.app import app


@pytest.fixture
def transport():
    return ASGITransport(app=app)


# ---------------------------------------------------------------------------
# Individual header checks
# ---------------------------------------------------------------------------

@pytest.mark.asyncio
async def test_x_content_type_options(transport):
    """Response must include X-Content-Type-Options: nosniff."""
    async with httpx.AsyncClient(transport=transport, base_url="http://test") as c:
        resp = await c.get("/")

    assert resp.headers.get("x-content-type-options") == "nosniff"


@pytest.mark.asyncio
async def test_x_frame_options(transport):
    """Response must include X-Frame-Options: DENY."""
    async with httpx.AsyncClient(transport=transport, base_url="http://test") as c:
        resp = await c.get("/")

    assert resp.headers.get("x-frame-options") == "DENY"


@pytest.mark.asyncio
async def test_strict_transport_security(transport):
    """Response must include Strict-Transport-Security header."""
    async with httpx.AsyncClient(transport=transport, base_url="http://test") as c:
        resp = await c.get("/")

    hsts = resp.headers.get("strict-transport-security")
    assert hsts is not None, "Strict-Transport-Security header missing"
    assert "max-age=" in hsts
    # Recommended: at least 1 year (31536000 seconds)
    # Extract max-age value
    for part in hsts.split(";"):
        part = part.strip()
        if part.startswith("max-age="):
            max_age = int(part.split("=")[1])
            assert max_age >= 31536000, (
                f"HSTS max-age should be >= 31536000 (1 year), got {max_age}"
            )


@pytest.mark.asyncio
async def test_content_security_policy(transport):
    """Response must include Content-Security-Policy header."""
    async with httpx.AsyncClient(transport=transport, base_url="http://test") as c:
        resp = await c.get("/")

    csp = resp.headers.get("content-security-policy")
    assert csp is not None, "Content-Security-Policy header missing"
    assert "default-src" in csp, "CSP must define default-src directive"


# ---------------------------------------------------------------------------
# Headers present on all response types
# ---------------------------------------------------------------------------

@pytest.mark.asyncio
async def test_security_headers_on_error_responses(transport):
    """Security headers must also be present on error responses (404)."""
    async with httpx.AsyncClient(transport=transport, base_url="http://test") as c:
        resp = await c.get("/nonexistent-endpoint-12345")

    assert resp.headers.get("x-content-type-options") == "nosniff"
    assert resp.headers.get("x-frame-options") == "DENY"


@pytest.mark.asyncio
async def test_security_headers_on_post_endpoint(transport):
    """Security headers must be present on POST responses too."""
    async with httpx.AsyncClient(transport=transport, base_url="http://test") as c:
        resp = await c.post("/predict", json={
            "home_team": "LG",
            "away_team": "KT",
            "date": "2025-04-01",
        })

    # Even if the request fails (e.g., models not loaded), headers must be set
    assert resp.headers.get("x-content-type-options") == "nosniff"
    assert resp.headers.get("x-frame-options") == "DENY"


@pytest.mark.asyncio
async def test_no_server_version_disclosure(transport):
    """The Server header should not reveal detailed version info."""
    async with httpx.AsyncClient(transport=transport, base_url="http://test") as c:
        resp = await c.get("/")

    server = resp.headers.get("server", "")
    # Should not contain version numbers like "uvicorn/0.30.0"
    assert "/" not in server or server == "", (
        f"Server header should not disclose version info, got: {server}"
    )
