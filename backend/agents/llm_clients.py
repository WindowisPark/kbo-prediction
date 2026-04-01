"""
멀티 LLM 클라이언트 — 3-provider 통합 인터페이스.

에이전트별 최적 모델 배정 (논문 기반):
  - Analyst: Gemini 2.5 Flash (수학/추론 A, 저비용)
  - Scout: GPT-4o (한국어 A+, KBO 도메인 지식)
  - Critic: Claude Sonnet 4 (비판적 사고 A+, sycophancy 방지)
  - Synthesizer: Gemini 2.5 Flash (JSON 안정적, 극저비용)

3-provider 다양성: Google + OpenAI + Anthropic
ReConcile 논문: 다른 모델 3개 > 같은 모델 5개
"""
import os
import time
import logging
from pathlib import Path
from dotenv import load_dotenv

load_dotenv(Path(__file__).parent.parent.parent / ".env", override=True)
logger = logging.getLogger(__name__)


class ClaudeClient:
    def __init__(self, model: str = "claude-sonnet-4-20250514", temperature: float = 0.4):
        from anthropic import Anthropic
        self.client = Anthropic(api_key=os.getenv("ANTHROPIC_API_KEY"))
        self.model = model
        self.temperature = temperature
        self.provider = f"anthropic/{model.split('-')[1]}"

    def chat(self, system: str, user_msg: str, max_tokens: int = 1024) -> str:
        for attempt in range(3):
            try:
                response = self.client.messages.create(
                    model=self.model,
                    max_tokens=max_tokens,
                    temperature=self.temperature,
                    system=system,
                    messages=[{"role": "user", "content": user_msg}],
                )
                usage = response.usage
                logger.debug(f"Claude tokens: {usage.input_tokens}in + {usage.output_tokens}out")
                return response.content[0].text
            except Exception as e:
                if attempt < 2:
                    wait = 2 ** (attempt + 1)
                    logger.warning(f"Claude error (attempt {attempt+1}): {e}. Retry in {wait}s")
                    time.sleep(wait)
                else:
                    raise


class GPTClient:
    def __init__(self, model: str = "gpt-4o", temperature: float = 0.4):
        from openai import OpenAI
        self.client = OpenAI(api_key=os.getenv("OPENAI_API_KEY"))
        self.model = model
        self.temperature = temperature
        self.provider = f"openai/{model}"

    def chat(self, system: str, user_msg: str, max_tokens: int = 1024) -> str:
        for attempt in range(3):
            try:
                response = self.client.chat.completions.create(
                    model=self.model,
                    max_tokens=max_tokens,
                    temperature=self.temperature,
                    messages=[
                        {"role": "system", "content": system},
                        {"role": "user", "content": user_msg},
                    ],
                )
                usage = response.usage
                logger.debug(f"GPT tokens: {usage.prompt_tokens}in + {usage.completion_tokens}out")
                return response.choices[0].message.content
            except Exception as e:
                if attempt < 2:
                    wait = 2 ** (attempt + 1)
                    logger.warning(f"GPT error (attempt {attempt+1}): {e}. Retry in {wait}s")
                    time.sleep(wait)
                else:
                    raise


class GeminiClient:
    def __init__(self, model: str = "gemini-2.5-flash", temperature: float = 0.4):
        from google import genai
        self.client = genai.Client(api_key=os.getenv("GOOGLE_API_KEY"))
        self.model = model
        self.temperature = temperature
        self.provider = f"gemini/{model}"

    def chat(self, system: str, user_msg: str, max_tokens: int = 1024) -> str:
        from google.genai import types
        for attempt in range(3):
            try:
                config = types.GenerateContentConfig(
                    system_instruction=system,
                    temperature=self.temperature,
                    max_output_tokens=max(max_tokens, 4096),
                    thinking_config=types.ThinkingConfig(thinking_budget=1024),
                )
                response = self.client.models.generate_content(
                    model=self.model,
                    contents=user_msg,
                    config=config,
                )
                text = response.text or ""
                if not text and response.candidates:
                    # thinking model이 출력 없이 끝난 경우
                    for part in response.candidates[0].content.parts:
                        if hasattr(part, "text") and part.text:
                            text = part.text
                            break
                logger.debug(f"Gemini response: {len(text)} chars")
                return text
            except Exception as e:
                if attempt < 2:
                    wait = 2 ** (attempt + 1)
                    logger.warning(f"Gemini error (attempt {attempt+1}): {e}. Retry in {wait}s")
                    time.sleep(wait)
                else:
                    raise


# 싱글턴 캐시
_client_cache: dict[str, ClaudeClient | GPTClient | GeminiClient] = {}

AGENT_CONFIG: dict[str, dict] = {
    "Analyst":     {"factory": lambda t: GeminiClient("gemini-2.5-pro", t),   "temperature": 0.4},
    "Scout":       {"factory": lambda t: GPTClient("gpt-4o", t),              "temperature": 0.4},
    "Critic":      {"factory": lambda t: ClaudeClient("claude-sonnet-4-20250514", t), "temperature": 0.4},
    "Synthesizer": {"factory": lambda t: GeminiClient("gemini-2.5-flash", t), "temperature": 0.1},
}


def get_client(agent_name: str):
    if agent_name not in _client_cache:
        config = AGENT_CONFIG.get(agent_name, {"factory": lambda t: GeminiClient(temperature=t), "temperature": 0.4})
        _client_cache[agent_name] = config["factory"](config["temperature"])
    return _client_cache[agent_name]
