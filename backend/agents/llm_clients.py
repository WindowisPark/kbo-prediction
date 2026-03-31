"""
멀티 LLM 클라이언트 — Claude + GPT 통합 인터페이스.

개선:
  - 싱글턴 캐시 (커넥션 풀 재사용)
  - 재시도 로직 (3회, exponential backoff)
  - Temperature 제어 (에이전트별)
  - 토큰 사용량 로깅
"""
import os
import time
import logging
from pathlib import Path
from dotenv import load_dotenv

load_dotenv(Path(__file__).parent.parent.parent / ".env", override=True)
logger = logging.getLogger(__name__)


class ClaudeClient:
    def __init__(self, model: str = "claude-3-haiku-20240307", temperature: float = 0.4):
        from anthropic import Anthropic
        self.client = Anthropic(api_key=os.getenv("ANTHROPIC_API_KEY"))
        self.model = model
        self.temperature = temperature
        self.provider = f"claude/{model.split('-')[2]}"

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
                    logger.warning(f"Claude API error (attempt {attempt+1}): {e}. Retrying in {wait}s...")
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
                    logger.warning(f"GPT API error (attempt {attempt+1}): {e}. Retrying in {wait}s...")
                    time.sleep(wait)
                else:
                    raise


# 싱글턴 캐시
_client_cache: dict[str, ClaudeClient | GPTClient] = {}

AGENT_CONFIG: dict[str, dict] = {
    "Analyst":     {"factory": lambda t: GPTClient("gpt-4o", t),         "temperature": 0.4},
    "Scout":       {"factory": lambda t: ClaudeClient(temperature=t),    "temperature": 0.4},
    "Critic":      {"factory": lambda t: GPTClient("gpt-4-turbo", t),    "temperature": 0.4},
    "Synthesizer": {"factory": lambda t: GPTClient("gpt-4o", t),         "temperature": 0.1},
}


def get_client(agent_name: str):
    if agent_name not in _client_cache:
        config = AGENT_CONFIG.get(agent_name, {"factory": lambda t: ClaudeClient(temperature=t), "temperature": 0.4})
        _client_cache[agent_name] = config["factory"](config["temperature"])
    return _client_cache[agent_name]
