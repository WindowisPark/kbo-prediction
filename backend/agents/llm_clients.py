"""
OpenRouter 단일 게이트웨이 LLM 클라이언트.

3사 모델을 OpenAI 호환 API 하나로 호출 (API 키/결제 계정 1개):
  - Analyst: google/gemini-2.5-flash (수학/추론, 저비용)
  - Scout: openai/gpt-4.1-mini (한국어/KBO 도메인, 저비용)
  - Critic: anthropic/claude-haiku-4.5 (비판적 사고, sycophancy 방지)
  - Synthesizer: google/gemini-2.5-flash (JSON 안정적)

3-provider 다양성 유지 (ReConcile 논문: 다른 모델 3개 > 같은 모델 5개)

비용 추적: 요청에 usage.include를 켜면 OpenRouter가 응답에 실비용(USD)을
포함해 주므로 단가표 계산 없이 정확한 비용이 LLMCostLog에 기록됨.
모델별 지출은 OpenRouter 대시보드(openrouter.ai/activity)에서도 확인 가능.

필수 환경변수: OPENROUTER_API_KEY
"""
import os
import time
import logging
from pathlib import Path
from dotenv import load_dotenv

load_dotenv(Path(__file__).parent.parent.parent / ".env", override=True)
logger = logging.getLogger(__name__)

from backend.utils.cost_tracker import log_cost

OPENROUTER_BASE_URL = "https://openrouter.ai/api/v1"

# 503/429 등 일시적 에러 판별
_TRANSIENT_KEYWORDS = ("503", "429", "UNAVAILABLE", "overloaded", "rate limit", "quota")

# 결제/크레딧 문제 판별 — 재시도 무의미. 즉시 실패시키고 어느 모델인지 명확히 로그.
# (OpenRouter: 402 insufficient credits / 공통: billing, payment)
_BILLING_KEYWORDS = (
    "insufficient_quota", "exceeded your current quota",
    "insufficient credits", "credit balance", "billing", "payment", "402",
)


def _is_transient(exc: Exception) -> bool:
    msg = str(exc)
    return any(kw in msg for kw in _TRANSIENT_KEYWORDS)


def _is_billing(exc: Exception) -> bool:
    msg = str(exc).lower()
    if "per minute" in msg or "per min" in msg:  # 분당 rate limit은 결제 문제 아님 → 재시도 대상
        return False
    return any(kw in msg for kw in _BILLING_KEYWORDS)


def _log_call_error(provider: str, exc: Exception, attempt: int, max_retries: int) -> None:
    """호출 실패를 provider/사유가 grep 가능한 형태로 기록."""
    if _is_billing(exc):
        logger.error(f"[LLM-BILLING] {provider} 결제/크레딧 문제 — 재시도 생략: {exc}")
    else:
        logger.error(f"[LLM-FAIL] {provider} 호출 실패 (attempt {attempt + 1}/{max_retries}): {exc}")


# OpenAI SDK 클라이언트 싱글턴 (모든 모델이 같은 엔드포인트 사용)
_sdk_client = None


def _sdk():
    global _sdk_client
    if _sdk_client is None:
        from openai import OpenAI
        _sdk_client = OpenAI(
            base_url=OPENROUTER_BASE_URL,
            api_key=os.getenv("OPENROUTER_API_KEY"),
        )
    return _sdk_client


class OpenRouterClient:
    """OpenRouter 경유 단일 클라이언트. model은 슬러그 형식 (예: anthropic/claude-haiku-4.5)."""

    def __init__(self, model: str, temperature: float = 0.4):
        self.model = model
        self.temperature = temperature
        self.provider = model  # 로그 표시용. split("/")[0] → 원 제공사(google/openai/anthropic)

    def chat(self, system: str, user_msg: str, max_tokens: int = 1024) -> str:
        max_retries = 5
        for attempt in range(max_retries):
            try:
                response = _sdk().chat.completions.create(
                    model=self.model,
                    max_tokens=max_tokens,
                    temperature=self.temperature,
                    messages=[
                        {"role": "system", "content": system},
                        {"role": "user", "content": user_msg},
                    ],
                    extra_headers={"X-Title": "KBO AI Analyzer"},
                    extra_body={"usage": {"include": True}},  # 응답에 실비용(USD) 포함
                )
                usage = response.usage
                cost = getattr(usage, "cost", None)  # OpenRouter 실비용. 없으면 단가표로 계산
                log_cost(self.model, usage.prompt_tokens, usage.completion_tokens,
                         "openrouter", cost_usd=cost)
                return response.choices[0].message.content
            except Exception as e:
                if not _is_billing(e) and attempt < max_retries - 1 and _is_transient(e):
                    wait = min(2 ** (attempt + 1), 32)
                    logger.warning(f"OpenRouter {self.model} error (attempt {attempt+1}/{max_retries}): {e}. Retry in {wait}s")
                    time.sleep(wait)
                else:
                    _log_call_error(self.provider, e, attempt, max_retries)
                    raise


# 모델 fallback 매핑: primary 모델 실패 시 다른 제공사 모델로 전환
# (제공사 단위 장애는 OpenRouter가 자체 라우팅으로 흡수, 이건 모델 단위 안전망)
_FALLBACK_MAP = {
    "google": lambda temp: OpenRouterClient("anthropic/claude-haiku-4.5", temp),
    "openai": lambda temp: OpenRouterClient("anthropic/claude-haiku-4.5", temp),
    "anthropic": lambda temp: OpenRouterClient("openai/gpt-4.1-mini", temp),
}


# 싱글턴 캐시
_client_cache: dict[str, OpenRouterClient] = {}

AGENT_CONFIG: dict[str, dict] = {
    "Analyst":     {"model": "google/gemini-2.5-flash",      "temperature": 0.4},
    "Scout":       {"model": "openai/gpt-4.1-mini",          "temperature": 0.4},
    "Critic":      {"model": "anthropic/claude-haiku-4.5",   "temperature": 0.4},
    "Synthesizer": {"model": "google/gemini-2.5-flash",      "temperature": 0.1},
}


def get_client(agent_name: str) -> OpenRouterClient:
    if agent_name not in _client_cache:
        config = AGENT_CONFIG.get(
            agent_name, {"model": "google/gemini-2.5-flash", "temperature": 0.4}
        )
        _client_cache[agent_name] = OpenRouterClient(config["model"], config["temperature"])
    return _client_cache[agent_name]


def chat_with_fallback(client: OpenRouterClient, system: str, user_msg: str, max_tokens: int = 1024) -> str:
    """Primary 모델로 호출 시도, 실패 시 다른 제공사 모델로 fallback."""
    try:
        return client.chat(system, user_msg, max_tokens)
    except Exception as e:
        provider_key = client.provider.split("/")[0]  # "google", "openai", "anthropic"
        fallback_factory = _FALLBACK_MAP.get(provider_key)
        if fallback_factory is None:
            raise
        fallback_client = fallback_factory(client.temperature)
        logger.warning(
            f"[LLM-FALLBACK] {client.provider} 실패 → {fallback_client.provider}로 대체. 원인: {e}"
        )
        try:
            return fallback_client.chat(system, user_msg, max_tokens)
        except Exception as e2:
            logger.error(
                f"[LLM-FAIL] fallback {fallback_client.provider}도 실패 "
                f"(primary: {client.provider}): {e2}"
            )
            raise
