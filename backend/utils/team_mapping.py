"""팀명 통합 매핑 — 역대 팀명 변경을 하나로 통합."""

# 팀명 → 통합 코드
TEAM_UNIFY = {
    # 히어로즈 계보: 현대(~2007) → 우리(2008) → 히어로즈(2008~) → 넥센(2010~) → 키움(2019~)
    "현대": "Heroes",
    "우리": "Heroes",
    "히어로즈": "Heroes",
    "넥센": "Heroes",
    "키움": "Heroes",
    # SK → SSG (2021~)
    "SK": "SSG",
    # 해태 → KIA (2001~) — 2000년 이후 데이터에서는 거의 KIA
    "해태": "KIA",
}

# 현재(2025) 활동중인 10개 팀
CURRENT_TEAMS = ["KIA", "KT", "LG", "NC", "SSG", "두산", "롯데", "삼성", "Heroes", "한화"]


def unify_team(name: str) -> str:
    """팀명을 통합 코드로 변환."""
    return TEAM_UNIFY.get(name, name)
