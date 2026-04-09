"""
멀티 에이전트 토론 파이프라인 — 멀티 모델 버전.

구조 (Du et al. 2023 + ReConcile 방식):
  Phase 1: 독립 분석 (3 에이전트, 각각 다른 LLM)
  Phase 2: 토론 (2 라운드, 동시생성→수정)
  Phase 3: Synthesizer가 최종 종합

모델 배정 (3-provider 다양성):
  - Analyst (Gemini 2.5 Pro): 수학/추론, 통계 분석
  - Scout (GPT-4o): 한국어 맥락, KBO 도메인 지식
  - Critic (Claude Sonnet 4): 비판적 사고, sycophancy 방지
  - Synthesizer (Gemini 2.5 Flash): JSON 출력, 종합
"""
import json
import re
import logging
from dataclasses import dataclass, field

from .llm_clients import get_client, chat_with_fallback
from .prompts import (
    ANALYST_SYSTEM, SCOUT_SYSTEM, CRITIC_SYSTEM,
    SYNTHESIZER_SYSTEM, DEBATE_ROUND_PROMPT,
)

logger = logging.getLogger(__name__)


@dataclass
class GameContext:
    """경기 정보 + ML 모델 출력."""
    home_team: str
    away_team: str
    date: str
    xgboost_prob: float
    elo_prob: float
    bayesian_prob: float
    ensemble_prob: float = 0.5
    home_elo: float = 1500
    away_elo: float = 1500
    home_win_pct_10: float = 0.5
    away_win_pct_10: float = 0.5
    home_streak: int = 0
    away_streak: int = 0
    home_ops: float = 0.0
    away_ops: float = 0.0
    home_era: float = 0.0
    away_era: float = 0.0
    h2h_win_pct: float = 0.5
    home_rank: int = 0
    away_rank: int = 0
    extra_context: str = ""

    def to_prompt(self) -> str:
        return f"""## 경기 정보
- 날짜: {self.date}
- 홈팀: {self.home_team}
- 원정팀: {self.away_team}

## ML 모델 분석 (홈팀 승리 확률)
- XGBoost: {self.xgboost_prob:.3f}
- ELO: {self.elo_prob:.3f}
- Ensemble: {self.bayesian_prob:.3f}
- **AI 종합: {self.ensemble_prob:.3f}**

## 팀 데이터
| 지표 | {self.home_team} (홈) | {self.away_team} (원정) |
|------|:---:|:---:|
| 현재 순위 | {self.home_rank}위 | {self.away_rank}위 |
| ELO 레이팅 | {self.home_elo:.0f} | {self.away_elo:.0f} |
| 최근 10경기 승률 | {self.home_win_pct_10:.3f} | {self.away_win_pct_10:.3f} |
| 연승/연패 | {self.home_streak:+d} | {self.away_streak:+d} |
| 팀 OPS | {self.home_ops:.3f} | {self.away_ops:.3f} |
| 팀 ERA | {self.home_era:.2f} | {self.away_era:.2f} |
| 상대전적 (홈팀 기준) | {self.h2h_win_pct:.3f} | - |
{self.extra_context}"""


@dataclass
class AgentResponse:
    """에이전트 응답."""
    agent_name: str
    model_provider: str  # "claude" or "gpt"
    round_num: int
    content: str
    probability: float = 0.5
    confidence: str = "medium"


@dataclass
class DebateResult:
    """토론 최종 결과."""
    home_team: str
    away_team: str
    home_win_probability: float
    confidence: str
    predicted_winner: str
    key_factors: list[str]
    reasoning: str
    debate_log: list[dict] = field(default_factory=list)
    model_probabilities: dict = field(default_factory=dict)


def _extract_probability(text: str) -> float:
    """응답에서 확률 추출."""
    patterns = [
        r"홈팀 승리 확률[:\s]*([0-9.]+)",
        r"확률[:\s]*([0-9.]+)",
        r"home_win_probability[\":\s]*([0-9.]+)",
        r"probability[:\s]*([0-9.]+)",
    ]
    for pattern in patterns:
        match = re.search(pattern, text)
        if match:
            prob = float(match.group(1))
            if 0 <= prob <= 1:
                return prob
    # 마지막 시도: 0.XXX 패턴 (ERA/OPS와 혼동 가능성 있음)
    all_probs = re.findall(r"0\.\d{2,3}", text)
    if all_probs:
        val = float(all_probs[-1])
        logger.warning(f"Probability extracted via generic fallback: {val} (may be inaccurate)")
        return val
    return 0.5


def _extract_confidence(text: str) -> str:
    """응답에서 신뢰도 추출."""
    text_lower = text.lower()
    if "high" in text_lower or "높" in text_lower:
        return "high"
    elif "low" in text_lower or "낮" in text_lower:
        return "low"
    return "medium"


class DebatePipeline:
    """멀티 모델 에이전트 토론 파이프라인."""

    def __init__(self, debate_rounds: int = 2):
        self.debate_rounds = debate_rounds
        self.agents = {
            "Analyst": {"system": ANALYST_SYSTEM},
            "Scout": {"system": SCOUT_SYSTEM},
            "Critic": {"system": CRITIC_SYSTEM},
        }

    def _call_agent(self, agent_name: str, user_msg: str) -> tuple[str, str]:
        """에이전트에 맞는 LLM으로 호출. (응답, provider) 반환."""
        client = get_client(agent_name)
        system = self.agents.get(agent_name, {}).get("system", "")
        if not system:
            system = SYNTHESIZER_SYSTEM
        response = chat_with_fallback(client, system, user_msg)
        return response, client.provider

    def run_phase1(self, context: GameContext) -> list[AgentResponse]:
        """Phase 1: 독립 분석 — 3 에이전트 병렬 실행."""
        from concurrent.futures import ThreadPoolExecutor, as_completed
        prompt = context.to_prompt()

        def call(name):
            content, provider = self._call_agent(name, f"다음 경기를 분석하세요:\n\n{prompt}")
            resp = AgentResponse(
                agent_name=name, model_provider=provider, round_num=0,
                content=content, probability=_extract_probability(content),
                confidence=_extract_confidence(content),
            )
            logger.info(f"  Phase1 {name} ({provider}): prob={resp.probability:.3f}")
            return resp

        logger.info("Phase 1 - 3 agents in parallel")
        with ThreadPoolExecutor(max_workers=3) as pool:
            futures = {pool.submit(call, name): name for name in self.agents}
            responses = [f.result() for f in as_completed(futures)]

        return sorted(responses, key=lambda r: list(self.agents.keys()).index(r.agent_name))

    def run_phase2(self, context: GameContext, prev_responses: list[AgentResponse]) -> list[AgentResponse]:
        """Phase 2: 토론 라운드 — 각 라운드 내 3 에이전트 병렬."""
        from concurrent.futures import ThreadPoolExecutor, as_completed
        current = prev_responses

        for round_num in range(1, self.debate_rounds + 1):
            logger.info(f"Phase 2 - Round {round_num} (parallel)")

            def call(name, cur=current):
                others = [r for r in cur if r.agent_name != name]
                other_text = "\n\n".join([
                    f"### {r.agent_name} [{r.model_provider}] "
                    f"(Round {r.round_num}, 확률: {r.probability:.3f}, 신뢰도: {r.confidence})\n{r.content}"
                    for r in others
                ])
                debate_prompt = DEBATE_ROUND_PROMPT.format(other_analyses=other_text)
                full_prompt = f"원래 경기 정보:\n\n{context.to_prompt()}\n\n{debate_prompt}"
                content, provider = self._call_agent(name, full_prompt)
                resp = AgentResponse(
                    agent_name=name, model_provider=provider, round_num=round_num,
                    content=content, probability=_extract_probability(content),
                    confidence=_extract_confidence(content),
                )
                logger.info(f"  {name} ({provider}) R{round_num}: prob={resp.probability:.3f}")
                return resp

            with ThreadPoolExecutor(max_workers=3) as pool:
                futures = {pool.submit(call, name): name for name in self.agents}
                new_responses = [f.result() for f in as_completed(futures)]

            current = sorted(new_responses, key=lambda r: list(self.agents.keys()).index(r.agent_name))

        return current

    def run_phase3(self, context: GameContext, all_responses: list[AgentResponse]) -> DebateResult:
        """Phase 3: Synthesizer 종합."""
        logger.info("Phase 3 - Synthesizer")

        debate_summary = "\n\n".join([
            f"### {r.agent_name} [{r.model_provider}] "
            f"(Round {r.round_num}, 확률: {r.probability:.3f}, 신뢰도: {r.confidence})\n{r.content}"
            for r in all_responses
        ])

        prompt = f"""원래 경기 정보:

{context.to_prompt()}

---

## 토론 과정

{debate_summary}

---

위 토론을 종합하여 최종 예측을 JSON 형식으로 출력하세요."""

        client = get_client("Synthesizer")
        content = chat_with_fallback(client, SYNTHESIZER_SYSTEM, prompt, max_tokens=2048)

        # JSON 파싱 — ```json 블록 우선, fallback으로 최대 {} 블록
        result = {}
        try:
            json_blocks = re.findall(r'```json\s*(.*?)\s*```', content, re.DOTALL)
            if json_blocks:
                result = json.loads(json_blocks[0])
            else:
                json_match = re.search(r'\{.*\}', content, re.DOTALL)
                if json_match:
                    result = json.loads(json_match.group())
        except json.JSONDecodeError:
            logger.warning(f"Synthesizer JSON 파싱 실패. Raw: {content[:200]}")

        debate_log = [
            {
                "agent": r.agent_name,
                "model": r.model_provider,
                "round": r.round_num,
                "probability": r.probability,
                "confidence": r.confidence,
                "content": r.content,
            }
            for r in all_responses
        ]
        debate_log.append({
            "agent": "Synthesizer",
            "model": client.provider,
            "round": "final",
            "content": content,
        })

        return DebateResult(
            home_team=context.home_team,
            away_team=context.away_team,
            home_win_probability=result.get("home_win_probability", 0.5),
            confidence=result.get("confidence", "medium"),
            predicted_winner=result.get("predicted_winner", ""),
            key_factors=result.get("key_factors", []),
            reasoning=result.get("reasoning", content),
            debate_log=debate_log,
            model_probabilities={
                "xgboost": context.xgboost_prob,
                "elo": context.elo_prob,
                "ensemble": context.bayesian_prob,
                "ai_combined": context.ensemble_prob,
            },
        )

    def predict(self, context: GameContext) -> DebateResult:
        """전체 파이프라인 실행."""
        logger.info(f"=== Debate: {context.away_team} @ {context.home_team} ({context.date}) ===")

        phase1 = self.run_phase1(context)
        phase2 = self.run_phase2(context, phase1)
        # Phase2만 Synthesizer에 전달 (Phase1은 이미 Phase2에 반영됨 — 토큰 절약)
        result = self.run_phase3(context, phase2)

        logger.info(
            f"Final: {result.predicted_winner} "
            f"({result.home_win_probability:.3f}, {result.confidence})"
        )
        return result
