"""
멀티 LLM 클라이언트 — Claude + GPT를 통합 인터페이스로.

에이전트별 다른 모델 배정:
  - Analyst: GPT-4o (가장 강력한 추론)
  - Scout: Claude Haiku (빠른 맥락 파악)
  - Critic: GPT-4-turbo (독립적 비판 시각)
  - Synthesizer: GPT-4o (종합 능력)

ReConcile 논문: 모델 다양성이 에이전트 수보다 중요
"""
import os
from pathlib import Path
from dotenv import load_dotenv

load_dotenv(Path(__file__).parent.parent.parent / ".env", override=True)


class ClaudeClient:
    """Anthropic Claude API 클라이언트."""

    def __init__(self, model: str = "claude-3-haiku-20240307"):
        from anthropic import Anthropic
        self.client = Anthropic(api_key=os.getenv("ANTHROPIC_API_KEY"))
        self.model = model
        self.provider = f"claude/{model.split('-')[2]}"

    def chat(self, system: str, user_msg: str, max_tokens: int = 1024) -> str:
        response = self.client.messages.create(
            model=self.model,
            max_tokens=max_tokens,
            system=system,
            messages=[{"role": "user", "content": user_msg}],
        )
        return response.content[0].text


class GPTClient:
    """OpenAI GPT API 클라이언트."""

    def __init__(self, model: str = "gpt-4o"):
        from openai import OpenAI
        self.client = OpenAI(api_key=os.getenv("OPENAI_API_KEY"))
        self.model = model
        self.provider = f"openai/{model}"

    def chat(self, system: str, user_msg: str, max_tokens: int = 1024) -> str:
        response = self.client.chat.completions.create(
            model=self.model,
            max_tokens=max_tokens,
            messages=[
                {"role": "system", "content": system},
                {"role": "user", "content": user_msg},
            ],
        )
        return response.choices[0].message.content


# 에이전트별 모델 배정 — 최대 다양성
AGENT_CONFIG = {
    "Analyst": lambda: GPTClient("gpt-4o"),          # GPT-4o: 강력한 데이터 분석
    "Scout": lambda: ClaudeClient(),                  # Claude Haiku: 빠른 맥락 파악
    "Critic": lambda: GPTClient("gpt-4-turbo"),       # GPT-4-turbo: 독립적 비판 시각
    "Synthesizer": lambda: GPTClient("gpt-4o"),       # GPT-4o: 종합 능력
}


def get_client(agent_name: str):
    """에이전트 이름에 맞는 LLM 클라이언트 생성."""
    factory = AGENT_CONFIG.get(agent_name, lambda: ClaudeClient())
    return factory()
