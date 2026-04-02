"""
Authentication Security Tests
===============================
Verify JWT-based authentication: registration, login, token lifecycle,
password hashing, and resistance to common attacks.

Security properties under test:
  - Registration creates a user and returns a JWT.
  - Duplicate email is rejected with 409.
  - Weak passwords are rejected (min 8 chars, at least one number).
  - Login returns access + refresh tokens for valid credentials.
  - Wrong password / non-existent email both return 401 with identical
    error messages (prevents user enumeration).
  - Refresh token flow works and rejects expired tokens.
  - JWT payload contains user_id, email, tier.
  - Access token expires in 30 min, refresh in 7 days.
  - Tampered JWTs are rejected.
  - SQL injection payloads in email/password are handled safely.
  - Passwords are stored as bcrypt hashes, never plaintext.

All tests are expected to FAIL until the auth system is implemented.
"""
import time
import json
import base64
import pytest
import httpx
from httpx import ASGITransport

from backend.api.app import app

from tests.conftest import register_user, login_user


@pytest.fixture
def transport():
    return ASGITransport(app=app)


def _decode_jwt_payload(token: str) -> dict:
    """Decode the payload section of a JWT without verification."""
    payload_b64 = token.split(".")[1]
    # Fix padding
    padding = 4 - len(payload_b64) % 4
    if padding != 4:
        payload_b64 += "=" * padding
    return json.loads(base64.urlsafe_b64decode(payload_b64))


# ---------------------------------------------------------------------------
# Registration
# ---------------------------------------------------------------------------

class TestRegistration:
    """POST /auth/register"""

    @pytest.mark.asyncio
    async def test_register_success(self, transport):
        """Successful registration returns 201 and a JWT access_token."""
        async with httpx.AsyncClient(transport=transport, base_url="http://test") as c:
            resp = await register_user(c, "newuser@test.com", "Secure123!")

        assert resp.status_code == 201
        data = resp.json()
        assert "access_token" in data
        assert "refresh_token" in data
        assert data["token_type"] == "bearer"

    @pytest.mark.asyncio
    async def test_register_duplicate_email_returns_409(self, transport):
        """Registering the same email twice must return 409 Conflict."""
        async with httpx.AsyncClient(transport=transport, base_url="http://test") as c:
            await register_user(c, "dup@test.com", "Secure123!")
            resp = await register_user(c, "dup@test.com", "Secure123!")

        assert resp.status_code == 409

    @pytest.mark.asyncio
    @pytest.mark.parametrize(
        "weak_password",
        [
            "short1",       # too short (<8 chars)
            "abcdefgh",     # no number
            "ABCDEFGH",     # no number
            "12345678",     # no letter — optional, but good practice
            "",             # empty
        ],
    )
    async def test_register_weak_password_rejected(self, transport, weak_password: str):
        """Passwords must be >= 8 chars and contain at least one number."""
        async with httpx.AsyncClient(transport=transport, base_url="http://test") as c:
            resp = await register_user(c, "weakpw@test.com", weak_password)

        assert resp.status_code == 422, (
            f"Weak password '{weak_password}' should be rejected with 422"
        )

    @pytest.mark.asyncio
    async def test_register_invalid_email_rejected(self, transport):
        """Invalid email format should be rejected."""
        async with httpx.AsyncClient(transport=transport, base_url="http://test") as c:
            resp = await register_user(c, "not-an-email", "Secure123!")

        assert resp.status_code == 422


# ---------------------------------------------------------------------------
# Login
# ---------------------------------------------------------------------------

class TestLogin:
    """POST /auth/login"""

    @pytest.mark.asyncio
    async def test_login_success(self, transport):
        """Valid credentials return access + refresh tokens."""
        async with httpx.AsyncClient(transport=transport, base_url="http://test") as c:
            await register_user(c, "login@test.com", "Secure123!")
            resp = await login_user(c, "login@test.com", "Secure123!")

        assert resp.status_code == 200
        data = resp.json()
        assert "access_token" in data
        assert "refresh_token" in data

    @pytest.mark.asyncio
    async def test_login_wrong_password_returns_401(self, transport):
        """Wrong password must return 401."""
        async with httpx.AsyncClient(transport=transport, base_url="http://test") as c:
            await register_user(c, "wrongpw@test.com", "Secure123!")
            resp = await login_user(c, "wrongpw@test.com", "WrongPass1!")

        assert resp.status_code == 401

    @pytest.mark.asyncio
    async def test_login_nonexistent_email_returns_401(self, transport):
        """Non-existent email must return 401 (not 404, to prevent enumeration)."""
        async with httpx.AsyncClient(transport=transport, base_url="http://test") as c:
            resp = await login_user(c, "ghost@test.com", "Secure123!")

        assert resp.status_code == 401

    @pytest.mark.asyncio
    async def test_login_error_messages_identical(self, transport):
        """Wrong password and non-existent email must return the same error
        message to prevent user enumeration."""
        async with httpx.AsyncClient(transport=transport, base_url="http://test") as c:
            await register_user(c, "enum@test.com", "Secure123!")
            wrong_pw_resp = await login_user(c, "enum@test.com", "WrongPass1!")
            no_user_resp = await login_user(c, "nouser@test.com", "Secure123!")

        assert wrong_pw_resp.status_code == no_user_resp.status_code == 401
        assert wrong_pw_resp.json()["detail"] == no_user_resp.json()["detail"], (
            "Error messages must be identical to prevent user enumeration"
        )


# ---------------------------------------------------------------------------
# JWT Token structure & expiry
# ---------------------------------------------------------------------------

class TestJWTToken:
    """JWT payload and expiry validation."""

    @pytest.mark.asyncio
    async def test_jwt_contains_required_claims(self, transport):
        """Access token payload must include user_id, email, and tier."""
        async with httpx.AsyncClient(transport=transport, base_url="http://test") as c:
            await register_user(c, "claims@test.com", "Secure123!")
            resp = await login_user(c, "claims@test.com", "Secure123!")

        token = resp.json()["access_token"]
        payload = _decode_jwt_payload(token)

        assert "user_id" in payload or "sub" in payload, "Missing user identifier"
        assert "email" in payload
        assert "tier" in payload
        assert payload["tier"] in ("free", "basic", "pro")

    @pytest.mark.asyncio
    async def test_access_token_expires_in_30_minutes(self, transport):
        """Access token exp claim should be ~30 minutes from now."""
        async with httpx.AsyncClient(transport=transport, base_url="http://test") as c:
            await register_user(c, "exp@test.com", "Secure123!")
            resp = await login_user(c, "exp@test.com", "Secure123!")

        token = resp.json()["access_token"]
        payload = _decode_jwt_payload(token)
        now = time.time()
        exp = payload["exp"]
        ttl_seconds = exp - now

        # Allow 60-second tolerance
        assert 1700 <= ttl_seconds <= 1860, (
            f"Access token TTL should be ~1800s (30min), got {ttl_seconds:.0f}s"
        )

    @pytest.mark.asyncio
    async def test_refresh_token_expires_in_7_days(self, transport):
        """Refresh token exp claim should be ~7 days from now."""
        async with httpx.AsyncClient(transport=transport, base_url="http://test") as c:
            await register_user(c, "refresh_exp@test.com", "Secure123!")
            resp = await login_user(c, "refresh_exp@test.com", "Secure123!")

        token = resp.json()["refresh_token"]
        payload = _decode_jwt_payload(token)
        now = time.time()
        exp = payload["exp"]
        ttl_seconds = exp - now

        expected = 7 * 24 * 60 * 60  # 604800
        # Allow 60-second tolerance
        assert expected - 60 <= ttl_seconds <= expected + 60, (
            f"Refresh token TTL should be ~604800s (7d), got {ttl_seconds:.0f}s"
        )

    @pytest.mark.asyncio
    async def test_new_user_defaults_to_free_tier(self, transport):
        """Newly registered users should have tier='free'."""
        async with httpx.AsyncClient(transport=transport, base_url="http://test") as c:
            resp = await register_user(c, "freetier@test.com", "Secure123!")

        token = resp.json()["access_token"]
        payload = _decode_jwt_payload(token)
        assert payload["tier"] == "free"


# ---------------------------------------------------------------------------
# Refresh token flow
# ---------------------------------------------------------------------------

class TestRefreshToken:
    """POST /auth/refresh"""

    @pytest.mark.asyncio
    async def test_refresh_returns_new_access_token(self, transport):
        """Valid refresh token should return a new access token."""
        async with httpx.AsyncClient(transport=transport, base_url="http://test") as c:
            await register_user(c, "refresh@test.com", "Secure123!")
            login_resp = await login_user(c, "refresh@test.com", "Secure123!")
            refresh_token = login_resp.json()["refresh_token"]

            resp = await c.post(
                "/auth/refresh",
                json={"refresh_token": refresh_token},
            )

        assert resp.status_code == 200
        assert "access_token" in resp.json()

    @pytest.mark.asyncio
    async def test_refresh_with_expired_token_returns_401(self, transport):
        """Expired refresh token must be rejected with 401."""
        # We simulate this by sending a clearly invalid/expired token.
        # The implementation should reject it.
        async with httpx.AsyncClient(transport=transport, base_url="http://test") as c:
            resp = await c.post(
                "/auth/refresh",
                json={"refresh_token": "expired.token.here"},
            )

        assert resp.status_code == 401

    @pytest.mark.asyncio
    async def test_refresh_with_access_token_rejected(self, transport):
        """Using an access token as refresh token must be rejected."""
        async with httpx.AsyncClient(transport=transport, base_url="http://test") as c:
            await register_user(c, "wrongtype@test.com", "Secure123!")
            login_resp = await login_user(c, "wrongtype@test.com", "Secure123!")
            access_token = login_resp.json()["access_token"]

            resp = await c.post(
                "/auth/refresh",
                json={"refresh_token": access_token},
            )

        assert resp.status_code == 401


# ---------------------------------------------------------------------------
# Token validation on protected endpoints
# ---------------------------------------------------------------------------

class TestTokenValidation:
    """Protected endpoints must reject invalid/tampered tokens."""

    @pytest.mark.asyncio
    async def test_tampered_jwt_rejected(self, transport):
        """A JWT with a modified payload must be rejected with 401."""
        async with httpx.AsyncClient(transport=transport, base_url="http://test") as c:
            await register_user(c, "tamper@test.com", "Secure123!")
            login_resp = await login_user(c, "tamper@test.com", "Secure123!")
            token = login_resp.json()["access_token"]

            # Tamper: flip a character in the payload section
            parts = token.split(".")
            payload_bytes = bytearray(
                base64.urlsafe_b64decode(parts[1] + "==")
            )
            payload_bytes[0] ^= 0xFF
            parts[1] = base64.urlsafe_b64encode(payload_bytes).decode().rstrip("=")
            tampered = ".".join(parts)

            resp = await c.get(
                "/standings",
                headers={"Authorization": f"Bearer {tampered}"},
            )

        assert resp.status_code == 401

    @pytest.mark.asyncio
    async def test_missing_auth_header_on_protected_endpoint(self, transport):
        """Protected endpoints without Authorization header should treat
        user as unauthenticated (Free tier), but still respond."""
        async with httpx.AsyncClient(transport=transport, base_url="http://test") as c:
            # /standings should work for free tier (unauthenticated)
            resp = await c.get("/standings")

        # Should not be 401 — unauthenticated users are treated as Free
        assert resp.status_code in (200, 500)  # 500 if models not loaded

    @pytest.mark.asyncio
    async def test_garbage_bearer_token_returns_401(self, transport):
        """Completely invalid token string must return 401."""
        async with httpx.AsyncClient(transport=transport, base_url="http://test") as c:
            resp = await c.get(
                "/standings",
                headers={"Authorization": "Bearer not.a.real.jwt"},
            )

        assert resp.status_code == 401


# ---------------------------------------------------------------------------
# SQL injection resistance
# ---------------------------------------------------------------------------

class TestSQLInjection:
    """Verify that SQL injection in auth fields is handled safely."""

    SQL_PAYLOADS = [
        "' OR 1=1 --",
        "'; DROP TABLE users; --",
        "admin@test.com' UNION SELECT * FROM users --",
        "1; SELECT * FROM information_schema.tables --",
    ]

    @pytest.mark.asyncio
    @pytest.mark.parametrize("payload", SQL_PAYLOADS)
    async def test_sql_injection_in_email(self, transport, payload: str):
        """SQL injection in email field must not cause 500 or data leak."""
        async with httpx.AsyncClient(transport=transport, base_url="http://test") as c:
            resp = await c.post(
                "/auth/login",
                json={"email": payload, "password": "Secure123!"},
            )

        # Should get 401 or 422, never 500
        assert resp.status_code in (401, 422), (
            f"SQL injection payload should be handled safely, got {resp.status_code}"
        )

    @pytest.mark.asyncio
    @pytest.mark.parametrize("payload", SQL_PAYLOADS)
    async def test_sql_injection_in_password(self, transport, payload: str):
        """SQL injection in password field must not cause 500."""
        async with httpx.AsyncClient(transport=transport, base_url="http://test") as c:
            resp = await c.post(
                "/auth/login",
                json={"email": "safe@test.com", "password": payload},
            )

        assert resp.status_code in (401, 422), (
            f"SQL injection payload should be handled safely, got {resp.status_code}"
        )


# ---------------------------------------------------------------------------
# Password storage
# ---------------------------------------------------------------------------

class TestPasswordStorage:
    """Verify passwords are stored as bcrypt hashes."""

    @pytest.mark.asyncio
    async def test_password_stored_as_bcrypt(self, transport):
        """After registration, the stored password must be a bcrypt hash.

        This test imports the User model directly and checks the DB.
        It will fail until the User model and DB are implemented.
        """
        from backend.auth.models import User
        from backend.auth.database import get_db_session

        async with httpx.AsyncClient(transport=transport, base_url="http://test") as c:
            await register_user(c, "hashcheck@test.com", "Secure123!")

        with get_db_session() as session:
            user = session.query(User).filter(User.email == "hashcheck@test.com").first()

        assert user is not None, "User should exist in DB"
        stored_password = user.password_hash
        assert stored_password.startswith("$2b$") or stored_password.startswith("$2a$"), (
            "Password must be stored as bcrypt hash"
        )
        assert stored_password != "Secure123!", "Password must never be stored as plaintext"
