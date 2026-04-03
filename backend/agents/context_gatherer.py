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
import logging
from datetime import datetime

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
) -> str:
    """데이터 + 선발투수 + 웹 맥락을 통합하여 반환."""
    parts = []

    # 1. 자체 데이터 기반
    data_ctx = gather_context_from_data(home_team, away_team, date, features_df, pitcher_df)
    if data_ctx:
        parts.append(data_ctx)

    # 2. 선발투수 상세
    if home_starter or away_starter:
        try:
            year = int(date[:4])
        except (ValueError, TypeError):
            year = 2026
        starter_ctx = gather_starter_context(
            home_starter, away_starter,
            home_team_raw or home_team,
            away_team_raw or away_team,
            year, pitcher_df,
        )
        if starter_ctx:
            parts.append(starter_ctx)

    # 3. LLM 기반 리서치
    if include_web:
        logger.info(f"Gathering web context for {away_team} @ {home_team}...")
        web_ctx = gather_context_from_web(home_team, away_team, date)
        if web_ctx:
            parts.append(web_ctx)

    return "\n".join(parts)
