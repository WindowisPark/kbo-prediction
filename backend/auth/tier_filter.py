"""구독 티어별 응답 필터링.

티어 설계:
  Free  — 1차 배치(선발투수) 결과만. 승리팀만 (확률 숨김), 요인 1줄.
  Basic — 2차 배치(실제 라인업) 결과. 확률 + 요인 3줄 + reasoning 200자.
  Pro   — 전체 + 수동 재분석 가능.
"""

REASONING_PREVIEW_LENGTH = 200


def filter_prediction_response(response: dict, tier: str) -> dict:
    """예측 응답을 티어에 따라 필터링."""
    if tier == "pro":
        response["tier"] = tier
        return response

    filtered = {
        "home_team": response.get("home_team"),
        "away_team": response.get("away_team"),
        "date": response.get("date", ""),
        "predicted_winner": response.get("predicted_winner"),
        "confidence": response.get("confidence"),
        "tier": tier,
    }

    if tier == "free":
        # 승리팀만 — 확률/모델/토론/reasoning 전부 숨김
        filtered["home_win_probability"] = None
        filtered["key_factors"] = (response.get("key_factors") or [])[:1]
        filtered["reasoning"] = None
        filtered["model_probabilities"] = None
        filtered["debate_log"] = []
    elif tier == "basic":
        # 확률 + 요인 3줄 + reasoning 앞 200자
        filtered["home_win_probability"] = response.get("home_win_probability")
        filtered["key_factors"] = (response.get("key_factors") or [])[:3]
        full_reasoning = response.get("reasoning") or ""
        if len(full_reasoning) > REASONING_PREVIEW_LENGTH:
            filtered["reasoning"] = full_reasoning[:REASONING_PREVIEW_LENGTH] + "..."
        else:
            filtered["reasoning"] = full_reasoning
        filtered["model_probabilities"] = None
        filtered["debate_log"] = []

    return filtered


def filter_accuracy_response(accuracy_data: dict, tier: str) -> dict:
    """적중률 통계를 티어에 따라 필터링."""
    if tier == "pro":
        return accuracy_data

    if tier == "free":
        # 전체 적중률 숫자만
        return {
            "total_predictions": accuracy_data.get("total_predictions", 0),
            "correct": accuracy_data.get("correct", 0),
            "accuracy": accuracy_data.get("accuracy", 0.0),
            "by_confidence": {},
            "tier": "free",
        }

    # basic: 7일 상세 (by_confidence 포함)
    return {
        **accuracy_data,
        "tier": "basic",
    }
