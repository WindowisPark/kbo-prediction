"""
Tier-Based Access Control Tests (v2)
======================================
새 티어 설계 반영:

Free  — 승리팀만 (확률 숨김), 요인 1줄, ML/토론 차단, 1차 배치만
Basic — 확률 + 요인 3줄 + reasoning 200자, ML 차단, 2차 배치
Pro   — 전체 + 재분석 가능

분석 횟수 제한:
  Free:  1회/일
  Basic: 5회/일
  Pro:   무제한

조회 API (standings, teams 등): 무제한
"""
import pytest
import httpx
from httpx import ASGITransport

from backend.api.app import app
from tests.conftest import register_user, login_user, get_auth_headers


@pytest.fixture
def transport():
    return ASGITransport(app=app)


PREDICT_BODY = {
    "home_team": "LG",
    "away_team": "KT",
    "date": "2025-04-01",
}


# ---------------------------------------------------------------------------
# Free tier
# ---------------------------------------------------------------------------

class TestFreeTier:
    """Free: 승리팀만, 확률 숨김, 요인 1줄, ML/토론 차단."""

    @pytest.mark.asyncio
    async def test_unauthenticated_treated_as_free(self, transport):
        """미인증 요청은 Free 티어 취급."""
        async with httpx.AsyncClient(transport=transport, base_url="http://test") as c:
            resp = await c.post("/predict", json=PREDICT_BODY)

        if resp.status_code == 200:
            data = resp.json()
            assert "predicted_winner" in data

    @pytest.mark.asyncio
    async def test_free_probability_hidden(self, async_client, free_token):
        """Free: 승률(home_win_probability) 숨김."""
        resp = await async_client.post(
            "/predict", json=PREDICT_BODY, headers=free_token,
        )
        if resp.status_code == 200:
            data = resp.json()
            assert data.get("home_win_probability") is None, (
                "Free tier should not see win probability"
            )

    @pytest.mark.asyncio
    async def test_free_key_factors_one_line(self, async_client, free_token):
        """Free: 핵심 요인 최대 1줄."""
        resp = await async_client.post(
            "/predict", json=PREDICT_BODY, headers=free_token,
        )
        if resp.status_code == 200:
            data = resp.json()
            factors = data.get("key_factors", [])
            assert len(factors) <= 1, (
                f"Free tier should get max 1 key factor, got {len(factors)}"
            )

    @pytest.mark.asyncio
    async def test_free_reasoning_hidden(self, async_client, free_token):
        """Free: reasoning 숨김."""
        resp = await async_client.post(
            "/predict", json=PREDICT_BODY, headers=free_token,
        )
        if resp.status_code == 200:
            data = resp.json()
            assert data.get("reasoning") is None, (
                "Free tier should not see reasoning"
            )

    @pytest.mark.asyncio
    async def test_free_ml_model_blocked(self, async_client, free_token):
        """Free: model_probabilities 차단."""
        resp = await async_client.post(
            "/predict", json=PREDICT_BODY, headers=free_token,
        )
        if resp.status_code == 200:
            data = resp.json()
            assert data.get("model_probabilities") is None

    @pytest.mark.asyncio
    async def test_free_debate_blocked(self, async_client, free_token):
        """Free: debate_log 차단."""
        resp = await async_client.post(
            "/predict", json=PREDICT_BODY, headers=free_token,
        )
        if resp.status_code == 200:
            data = resp.json()
            debate = data.get("debate_log")
            assert debate is None or debate == []

    @pytest.mark.asyncio
    async def test_free_reanalyze_forbidden(self, async_client, free_token):
        """Free: reanalyze=true 요청 시 403."""
        body = {**PREDICT_BODY, "reanalyze": True}
        resp = await async_client.post(
            "/predict", json=body, headers=free_token,
        )
        assert resp.status_code == 403


# ---------------------------------------------------------------------------
# Basic tier
# ---------------------------------------------------------------------------

class TestBasicTier:
    """Basic: 확률 + 요인 3줄 + reasoning 200자, ML/토론 차단."""

    @pytest.mark.asyncio
    async def test_basic_gets_probability(self, async_client, basic_token):
        """Basic: 승률 제공."""
        resp = await async_client.post(
            "/predict", json=PREDICT_BODY, headers=basic_token,
        )
        if resp.status_code == 200:
            data = resp.json()
            assert data.get("home_win_probability") is not None, (
                "Basic tier should see win probability"
            )

    @pytest.mark.asyncio
    async def test_basic_key_factors_three(self, async_client, basic_token):
        """Basic: 핵심 요인 최대 3줄."""
        resp = await async_client.post(
            "/predict", json=PREDICT_BODY, headers=basic_token,
        )
        if resp.status_code == 200:
            data = resp.json()
            factors = data.get("key_factors", [])
            assert len(factors) <= 3

    @pytest.mark.asyncio
    async def test_basic_reasoning_preview(self, async_client, basic_token):
        """Basic: reasoning은 200자 미리보기."""
        resp = await async_client.post(
            "/predict", json=PREDICT_BODY, headers=basic_token,
        )
        if resp.status_code == 200:
            data = resp.json()
            reasoning = data.get("reasoning", "")
            if reasoning:
                # 200자 + "..." = 최대 203자
                assert len(reasoning) <= 203, (
                    f"Basic reasoning should be <=200 chars preview, got {len(reasoning)}"
                )

    @pytest.mark.asyncio
    async def test_basic_ml_model_blocked(self, async_client, basic_token):
        """Basic: model_probabilities 차단."""
        resp = await async_client.post(
            "/predict", json=PREDICT_BODY, headers=basic_token,
        )
        if resp.status_code == 200:
            data = resp.json()
            assert data.get("model_probabilities") is None

    @pytest.mark.asyncio
    async def test_basic_debate_blocked(self, async_client, basic_token):
        """Basic: debate_log 차단."""
        resp = await async_client.post(
            "/predict", json=PREDICT_BODY, headers=basic_token,
        )
        if resp.status_code == 200:
            data = resp.json()
            debate = data.get("debate_log")
            assert debate is None or debate == []

    @pytest.mark.asyncio
    async def test_basic_reanalyze_forbidden(self, async_client, basic_token):
        """Basic: reanalyze=true 요청 시 403."""
        body = {**PREDICT_BODY, "reanalyze": True}
        resp = await async_client.post(
            "/predict", json=body, headers=basic_token,
        )
        assert resp.status_code == 403


# ---------------------------------------------------------------------------
# Pro tier
# ---------------------------------------------------------------------------

class TestProTier:
    """Pro: 전체 접근 + 재분석 가능."""

    @pytest.mark.asyncio
    async def test_pro_gets_probability(self, async_client, pro_token):
        """Pro: 승률 제공."""
        resp = await async_client.post(
            "/predict", json=PREDICT_BODY, headers=pro_token,
        )
        if resp.status_code == 200:
            data = resp.json()
            assert data.get("home_win_probability") is not None

    @pytest.mark.asyncio
    async def test_pro_gets_model_probabilities(self, async_client, pro_token):
        """Pro: ML 모델 상세."""
        resp = await async_client.post(
            "/predict", json=PREDICT_BODY, headers=pro_token,
        )
        if resp.status_code == 200:
            data = resp.json()
            assert data.get("model_probabilities") is not None

    @pytest.mark.asyncio
    async def test_pro_gets_debate_log(self, async_client, pro_token):
        """Pro: 토론 로그."""
        resp = await async_client.post(
            "/predict", json=PREDICT_BODY, headers=pro_token,
        )
        if resp.status_code == 200:
            data = resp.json()
            debate = data.get("debate_log")
            assert debate is not None and len(debate) > 0

    @pytest.mark.asyncio
    async def test_pro_gets_full_reasoning(self, async_client, pro_token):
        """Pro: 전체 reasoning."""
        resp = await async_client.post(
            "/predict", json=PREDICT_BODY, headers=pro_token,
        )
        if resp.status_code == 200:
            data = resp.json()
            reasoning = data.get("reasoning")
            assert reasoning is not None
            assert len(reasoning) > 0

    @pytest.mark.asyncio
    async def test_pro_reanalyze_allowed(self, async_client, pro_token):
        """Pro: reanalyze=true 허용 (403 아님)."""
        body = {**PREDICT_BODY, "reanalyze": True}
        resp = await async_client.post(
            "/predict", json=body, headers=pro_token,
        )
        # 모델 미로드 시 500이지만, 403은 아님
        assert resp.status_code != 403


# ---------------------------------------------------------------------------
# 일일 분석 횟수 제한
# ---------------------------------------------------------------------------

class TestPredictLimit:
    """분석 횟수: Free 1/일, Basic 5/일, Pro 무제한. 조회 API 무제한."""

    @pytest.mark.asyncio
    async def test_free_predict_limit_1_per_day(self, transport):
        """Free: 1일 1회 분석, 2번째 요청 시 429."""
        async with httpx.AsyncClient(transport=transport, base_url="http://test") as c:
            headers = await get_auth_headers(c, "limit_free@test.com", "Secure123!")

            # 1번째 → OK (200 or 500=models not loaded)
            r1 = await c.post("/predict", json=PREDICT_BODY, headers=headers)
            # 2번째 → 429
            r2 = await c.post("/predict", json=PREDICT_BODY, headers=headers)

        assert r2.status_code == 429
        assert "retry-after" in r2.headers

    @pytest.mark.asyncio
    async def test_basic_predict_limit_5_per_day(self, transport):
        """Basic: 5회까지 허용, 6번째 429."""
        async with httpx.AsyncClient(transport=transport, base_url="http://test") as c:
            headers = await get_auth_headers(c, "limit_basic@test.com", "Secure123!")
            await c.post("/admin/set-tier",
                         json={"email": "limit_basic@test.com", "tier": "basic"},
                         headers=headers)
            resp = await login_user(c, "limit_basic@test.com", "Secure123!")
            headers = {"Authorization": f"Bearer {resp.json()['access_token']}"}

            statuses = []
            for _ in range(6):
                r = await c.post("/predict", json=PREDICT_BODY, headers=headers)
                statuses.append(r.status_code)

            # 처음 5개는 429가 아님
            assert 429 not in statuses[:5], "Basic should allow 5 predictions/day"
            # 6번째는 429
            assert statuses[5] == 429

    @pytest.mark.asyncio
    async def test_standings_unlimited(self, transport):
        """조회 API는 무제한 — standings 15회 연속 OK."""
        async with httpx.AsyncClient(transport=transport, base_url="http://test") as c:
            headers = await get_auth_headers(c, "unlimited@test.com", "Secure123!")

            statuses = []
            for _ in range(15):
                r = await c.get("/standings", headers=headers)
                statuses.append(r.status_code)

        # 429가 하나도 없어야 함
        assert 429 not in statuses, "View APIs should not be rate-limited"

    @pytest.mark.asyncio
    async def test_429_includes_limit_info(self, transport):
        """429 응답에 limit/used/tier 정보 포함."""
        async with httpx.AsyncClient(transport=transport, base_url="http://test") as c:
            headers = await get_auth_headers(c, "info429@test.com", "Secure123!")

            await c.post("/predict", json=PREDICT_BODY, headers=headers)
            r = await c.post("/predict", json=PREDICT_BODY, headers=headers)

        if r.status_code == 429:
            data = r.json()
            assert "limit" in data
            assert "used" in data
            assert "tier" in data


# ---------------------------------------------------------------------------
# 적중률 통계 티어 필터링
# ---------------------------------------------------------------------------

class TestAccuracyTierFilter:
    """적중률: Free=전체숫자만, Basic=상세, Pro=전체."""

    @pytest.mark.asyncio
    async def test_free_accuracy_no_details(self, async_client, free_token):
        """Free: by_confidence 비어있음."""
        resp = await async_client.get("/accuracy", headers=free_token)
        if resp.status_code == 200:
            data = resp.json()
            assert data.get("tier") == "free"
            assert data.get("by_confidence") == {}

    @pytest.mark.asyncio
    async def test_unauthenticated_accuracy(self, transport):
        """미인증: Free 취급."""
        async with httpx.AsyncClient(transport=transport, base_url="http://test") as c:
            resp = await c.get("/accuracy")
        if resp.status_code == 200:
            data = resp.json()
            assert data.get("by_confidence") == {}
