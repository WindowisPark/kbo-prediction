"""
경기 예측 전 맥락 정보를 자동 수집하는 모듈.

수집 항목:
  1. 최근 경기 결과 (양 팀 각각 최근 5경기)
  2. 시즌 순위/성적
  3. 상대전적 (올시즌)
  4. 웹 검색으로 최신 뉴스 (부상, 트레이드, 용병, 선발투수 등)

이 맥락이 에이전트의 extra_context로 주입되어
ML 모델이 포착 못하는 현재 상황을 반영한다.
"""
import json
import logging
from datetime import datetime
from pathlib import Path

from .llm_clients import GPTClient

logger = logging.getLogger(__name__)


def gather_context_from_data(
    home_team: str,
    away_team: str,
    date: str,
    features_df=None,
    pitcher_df=None,
) -> str:
    """자체 데이터에서 맥락 정보 추출."""
    lines = []

    if features_df is not None and not features_df.empty:
        import pandas as pd

        # 최근 10경기 결과 (시즌 초에는 가용 경기만)
        for team, label in [(home_team, "홈"), (away_team, "원정")]:
            team_games = features_df[
                ((features_df["home_team"] == team) | (features_df["away_team"] == team))
            ].tail(10)

            if not team_games.empty:
                results = []
                for _, g in team_games.iterrows():
                    is_home = g["home_team"] == team
                    won = (is_home and g["home_win"] == 1) or (not is_home and g["home_win"] == 0)
                    opp = g["away_team"] if is_home else g["home_team"]
                    score = f"{g['home_score']}-{g['away_score']}" if is_home else f"{g['away_score']}-{g['home_score']}"
                    results.append(f"{'W' if won else 'L'} vs {opp} ({score})")

                n = len(results)
                lines.append(f"\n### {team} ({label}팀) 최근 {n}경기")
                for r in results:
                    lines.append(f"  - {r}")

        # 시즌 성적 요약
        try:
            year = int(date[:4])
            season_games = features_df[features_df["season"] == year]
            for team, label in [(home_team, "홈"), (away_team, "원정")]:
                home_games = season_games[season_games["home_team"] == team]
                away_games = season_games[season_games["away_team"] == team]
                total = len(home_games) + len(away_games)
                if total > 0:
                    wins = int(home_games["home_win"].sum() + (len(away_games) - away_games["home_win"].sum()))
                    losses = total - wins
                    lines.append(f"\n### {team} {year}시즌: {wins}승 {losses}패 ({wins/total:.3f})")
        except (ValueError, KeyError):
            pass

        # 올시즌 상대전적
        try:
            year = int(date[:4])
            h2h = features_df[
                (features_df["season"] == year) &
                (
                    ((features_df["home_team"] == home_team) & (features_df["away_team"] == away_team)) |
                    ((features_df["home_team"] == away_team) & (features_df["away_team"] == home_team))
                )
            ]
            if not h2h.empty:
                home_wins = 0
                for _, g in h2h.iterrows():
                    if g["home_team"] == home_team and g["home_win"] == 1:
                        home_wins += 1
                    elif g["away_team"] == home_team and g["home_win"] == 0:
                        home_wins += 1
                lines.append(f"\n### 올시즌 상대전적: {home_team} {home_wins}승 - {len(h2h)-home_wins}승 {away_team}")
        except (ValueError, KeyError):
            pass

    # standings.json 기반 KBO 순위표 (프론트엔드와 동일 소스)
    standings_file = Path(__file__).parent.parent.parent / "data" / "standings.json"
    if standings_file.exists():
        try:
            standings_data = json.loads(standings_file.read_text(encoding="utf-8"))
            standings = standings_data.get("teams", {})
            if standings:
                ranked = sorted(standings.items(),
                                key=lambda x: x[1].get("win_pct", 0), reverse=True)
                season = standings_data.get("season", datetime.now().year)
                lines.append(f"\n### {season} KBO 현재 순위표")
                for i, (team, s) in enumerate(ranked, 1):
                    streak = s.get("streak", 0)
                    if streak > 0:
                        streak_str = f"{streak}연승"
                    elif streak < 0:
                        streak_str = f"{abs(streak)}연패"
                    else:
                        streak_str = "-"
                    lines.append(
                        f"  {i}위 {team}: {s['wins']}승 {s['losses']}패 "
                        f"{s['draws']}무 (승률 {s['win_pct']:.3f}) {streak_str}"
                    )
        except (json.JSONDecodeError, KeyError):
            pass

    # 올시즌 팀 스탯 (에이전트 맥락용 — ML 피처와 별도)
    if pitcher_df is not None and not pitcher_df.empty:
        try:
            year = int(date[:4])
            for team, label in [(home_team, "홈"), (away_team, "원정")]:
                # 올시즌 투수 스탯
                tp = pitcher_df[(pitcher_df["Year"] == year) & (pitcher_df["Team"] == team)]
                if not tp.empty:
                    import pandas as pd
                    era = pd.to_numeric(tp["ERA"], errors="coerce").mean()
                    fip = pd.to_numeric(tp["FIP"], errors="coerce").mean()
                    war = pd.to_numeric(tp["WAR"], errors="coerce").sum()
                    lines.append(f"\n### {team} {year} 시즌 투수 현황: ERA {era:.2f}, FIP {fip:.2f}, WAR {war:.1f}")
        except (ValueError, KeyError):
            pass

    return "\n".join(lines)


def gather_context_from_web(home_team: str, away_team: str, date: str) -> str:
    """LLM에게 두 팀의 최신 상황을 요약하게 한다."""
    client = GPTClient("gpt-4o")

    prompt = f"""당신은 KBO 야구 리서치 에이전트입니다.
아래 두 팀의 **현재 상황**을 짧게 정리해주세요.

경기: {away_team} @ {home_team} ({date})

다음 항목을 각 팀별로 간결하게 (각 1-2문장):
1. 올시즌 주요 영입/방출 선수 (특히 외국인 선수)
2. 현재 부상자 명단 (알려진 경우)
3. 예상 선발투수 (알려진 경우)
4. 최근 팀 분위기/이슈

모르는 항목은 건너뛰세요. 추측하지 말고 알려진 사실만.
한국어로 답변하세요."""

    try:
        response = client.chat(
            "당신은 KBO 야구 전문 리서치 에이전트입니다. 알려진 사실만 간결하게 정리합니다.",
            prompt,
            max_tokens=512,
        )
        return f"\n### 최신 팀 동향 (AI 리서치)\n{response}"
    except Exception as e:
        logger.warning(f"Web context gathering failed: {e}")
        return ""


def gather_starter_context(
    home_starter: str,
    away_starter: str,
    home_team_raw: str,
    away_team_raw: str,
    year: int,
    pitcher_df=None,
) -> str:
    """선발투수 개인 스탯 + 외국인/신인 플래그 + 유사 외국인 투수 컨텍스트."""
    if pitcher_df is None or pitcher_df.empty:
        return ""

    from backend.utils.player_stats import lookup_starter, format_starter_info
    from backend.utils.foreign_pitcher_similarity import (
        build_foreign_pitcher_index,
        find_similar_pitchers,
        format_similar_pitchers_context,
    )

    lines = ["\n### 선발투수 상세"]

    away_info = lookup_starter(away_starter, away_team_raw, year, pitcher_df)
    lines.append(format_starter_info(away_info, "away"))

    home_info = lookup_starter(home_starter, home_team_raw, year, pitcher_df)
    lines.append(format_starter_info(home_info, "home"))

    # 데뷔 시즌 외국인 투수가 있으면 유사 선수 매칭 추가
    foreign_index = None
    for info in [away_info, home_info]:
        if info and info.get("is_debut_foreign"):
            if foreign_index is None:
                foreign_index = build_foreign_pitcher_index(pitcher_df)
            similar = find_similar_pitchers(info, foreign_index, k=5)
            if similar:
                lines.append("")
                lines.append(format_similar_pitchers_context(info["name"], similar))

    return "\n".join(lines)


def _parse_throw_hand(handedness: str) -> str:
    """'우투좌타' → '우', '좌투우타' → '좌'."""
    if not isinstance(handedness, str) or len(handedness) < 2:
        return ""
    return handedness[0]  # 첫 글자: 우 or 좌


def _parse_bat_hand(handedness: str) -> str:
    """'우투좌타' → '좌', '우투양타' → '양'."""
    if not isinstance(handedness, str) or len(handedness) < 4:
        return ""
    return handedness[2]  # 세 번째 글자: 우 or 좌 or 양


def gather_lineup_matchup_context(
    home_team: str,
    away_team: str,
    home_starter: str,
    away_starter: str,
    year: int,
    pitcher_df=None,
    batting_df=None,
) -> str:
    """
    예상 라인업 + 선발투수 좌우 매치업 분석 컨텍스트.

    선발투수의 투구 손잡이에 따라 상대 타선의 좌/우타 구성을 분석.
    """
    import pandas as pd

    if batting_df is None or batting_df.empty:
        return ""

    lines = []

    # 선발투수 좌/우 판별
    starter_hands = {}
    if pitcher_df is not None and not pitcher_df.empty:
        for starter, team_raw in [(home_starter, home_team), (away_starter, away_team)]:
            if not starter or starter == "TBD":
                continue
            match = pitcher_df[(pitcher_df["Name"] == starter) & (pitcher_df["Year"] == year)]
            if match.empty:
                match = pitcher_df[pitcher_df["Name"] == starter].sort_values("Year", ascending=False).head(1)
            if not match.empty:
                hand = _parse_throw_hand(str(match.iloc[0].get("Handedness", "")))
                if hand:
                    starter_hands[starter] = hand

    # 각 팀 타선의 좌/우타 분석
    for team, opp_starter, label in [
        (home_team, away_starter, "홈"),
        (away_team, home_starter, "원정"),
    ]:
        # 해당 팀 올시즌 타자 로스터
        team_batters = batting_df[
            (batting_df["Team"] == team) & (batting_df["Year"] == year)
        ]
        if team_batters.empty:
            # 전년도 fallback
            team_batters = batting_df[
                (batting_df["Team"] == team) & (batting_df["Year"] == year - 1)
            ]
        if team_batters.empty:
            continue

        # 타자별 좌/우/양타 분류
        bat_hands = {}
        for _, row in team_batters.iterrows():
            bh = _parse_bat_hand(str(row.get("Handedness", "")))
            if bh and row["Name"]:
                bat_hands[row["Name"]] = {
                    "bat_hand": bh,
                    "ops": row.get("OPS", 0),
                    "war": row.get("WAR", 0),
                    "avg": row.get("AVG", 0),
                }

        if not bat_hands:
            continue

        # 상대 선발 좌/우
        opp_hand = starter_hands.get(opp_starter, "")
        opp_hand_label = {"우": "우완", "좌": "좌완"}.get(opp_hand, "")

        # 타선 좌/우 비율
        left = sum(1 for v in bat_hands.values() if v["bat_hand"] == "좌")
        right = sum(1 for v in bat_hands.values() if v["bat_hand"] == "우")
        switch = sum(1 for v in bat_hands.values() if v["bat_hand"] == "양")
        total = len(bat_hands)

        # 주요 타자 OPS 기준 상위 9명
        top_batters = sorted(bat_hands.items(), key=lambda x: x[1]["ops"], reverse=True)[:9]

        section = [f"\n### {team} ({label}) 타선 좌우 구성"]
        section.append(f"  좌타 {left}명 / 우타 {right}명 / 양타 {switch}명 (로스터 {total}명)")

        if opp_hand_label:
            # 매치업 분석
            # 야구 일반 원칙: 좌타는 우완에 강하고, 우타는 좌완에 강함
            if opp_hand == "우":
                advantage = left + switch
                section.append(f"  상대 선발 {opp_starter}({opp_hand_label}) → "
                               f"좌타+양타 {advantage}명 유리 매치업")
            else:
                advantage = right + switch
                section.append(f"  상대 선발 {opp_starter}({opp_hand_label}) → "
                               f"우타+양타 {advantage}명 유리 매치업")

        # 주전급 타자 상세
        section.append(f"  주요 타자 (OPS 상위):")
        for name, stats in top_batters[:5]:
            bh = {"좌": "좌타", "우": "우타", "양": "양타"}.get(stats["bat_hand"], "?")
            ops = stats["ops"]
            matchup = ""
            if opp_hand:
                if (opp_hand == "우" and stats["bat_hand"] in ("좌", "양")):
                    matchup = " ★유리"
                elif (opp_hand == "좌" and stats["bat_hand"] in ("우", "양")):
                    matchup = " ★유리"
            section.append(f"    {name} ({bh}, OPS {ops:.3f}){matchup}")

        lines.extend(section)

    return "\n".join(lines)


def gather_full_context(
    home_team: str,
    away_team: str,
    date: str,
    features_df=None,
    include_web: bool = True,
    home_starter: str = "",
    away_starter: str = "",
    home_team_raw: str = "",
    away_team_raw: str = "",
    pitcher_df=None,
    batting_df=None,
) -> str:
    """데이터 + 선발투수 + 매치업 + 웹 맥락을 통합하여 반환."""
    parts = []

    # 1. 자체 데이터 기반
    data_ctx = gather_context_from_data(home_team, away_team, date, features_df, pitcher_df)
    if data_ctx:
        parts.append(data_ctx)

    # 2. 선발투수 상세
    try:
        year = int(date[:4])
    except (ValueError, TypeError):
        year = 2026

    if home_starter or away_starter:
        starter_ctx = gather_starter_context(
            home_starter, away_starter,
            home_team_raw or home_team,
            away_team_raw or away_team,
            year, pitcher_df,
        )
        if starter_ctx:
            parts.append(starter_ctx)

    # 3. 좌우 매치업 분석
    if home_starter or away_starter:
        matchup_ctx = gather_lineup_matchup_context(
            home_team, away_team,
            home_starter, away_starter,
            year, pitcher_df, batting_df,
        )
        if matchup_ctx:
            parts.append(matchup_ctx)

    # 4. LLM 기반 리서치
    if include_web:
        logger.info(f"Gathering web context for {away_team} @ {home_team}...")
        web_ctx = gather_context_from_web(home_team, away_team, date)
        if web_ctx:
            parts.append(web_ctx)

    return "\n".join(parts)
