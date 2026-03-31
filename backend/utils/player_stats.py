"""
선수 스탯 조회 + 외국인/신인 판별 모듈.

pitching CSV에서 선발투수 이름으로 개인 스탯을 조회하고,
Draft 컬럼에서 외국인/신인 여부를 판별한다.
"""
import re
import pandas as pd
import numpy as np
from pathlib import Path


def load_pitcher_data(csv_path: str | Path) -> pd.DataFrame:
    """투수 CSV를 로드하고 타입 정리."""
    df = pd.read_csv(csv_path)
    for col in ["ERA", "FIP", "WHIP", "WAR"]:
        df[col] = pd.to_numeric(df[col], errors="coerce")
    df["GS"] = pd.to_numeric(df["GS"], errors="coerce").fillna(0).astype(int)
    df["W"] = pd.to_numeric(df["W"], errors="coerce").fillna(0).astype(int)
    df["L"] = pd.to_numeric(df["L"], errors="coerce").fillna(0).astype(int)
    return df


def detect_foreign(draft: str) -> bool:
    """Draft 컬럼에서 외국인 선수 여부 판별."""
    if not isinstance(draft, str):
        return False
    return "자유선발" in draft or "외국인" in draft


def detect_rookie(draft: str, year: int) -> bool:
    """Draft 컬럼에서 신인 여부 판별 (드래프트 연도 == 현재 연도)."""
    if not isinstance(draft, str):
        return False
    match = re.match(r"(\d{2})\s", draft)
    if match:
        draft_year = 2000 + int(match.group(1))
        return draft_year == year
    return False


def is_debut_foreign(name: str, year: int, df: pd.DataFrame) -> bool:
    """외국인 선수의 KBO 데뷔 시즌 여부."""
    player_rows = df[df["Name"] == name]
    if player_rows.empty:
        return False
    # 외국인인지 확인
    any_foreign = player_rows["Draft"].apply(detect_foreign).any()
    if not any_foreign:
        return False
    # 현재 연도 이전에 KBO 기록이 있는지
    prior = player_rows[player_rows["Year"] < year]
    return prior.empty


def lookup_starter(
    name: str,
    team_raw: str,
    year: int,
    df: pd.DataFrame,
) -> dict | None:
    """
    선발투수 스탯 조회.

    Args:
        name: 투수 이름 (한글)
        team_raw: KBO API에서 받은 팀명 (raw, unify 전)
        year: 시즌 연도
        df: 투수 DataFrame

    Returns:
        {name, team, year, ERA, FIP, WHIP, WAR, GS, W, L,
         is_foreign, is_rookie, is_debut_foreign,
         prev_season: {...} or None}
    """
    if not name or name == "TBD":
        return None

    # 1차: name + team + year
    match = df[(df["Name"] == name) & (df["Team"] == team_raw) & (df["Year"] == year)]

    # 2차: name + year (트레이드 대응)
    if match.empty:
        match = df[(df["Name"] == name) & (df["Year"] == year)]
        if len(match) > 1:
            match = match.sort_values("GS", ascending=False).head(1)

    # 3차: name만 (올시즌 아직 기록 없는 경우 — 최근 시즌)
    if match.empty:
        match = df[df["Name"] == name].sort_values("Year", ascending=False).head(1)
        if not match.empty and match.iloc[0]["Year"] < year - 2:
            match = pd.DataFrame()  # 2년 이상 전 기록은 무시

    if match.empty:
        return None

    row = match.iloc[0]
    draft = str(row.get("Draft", ""))
    foreign = detect_foreign(draft)
    rookie = detect_rookie(draft, year)
    debut_foreign = is_debut_foreign(name, year, df)

    result = {
        "name": name,
        "team": team_raw,
        "stats_year": int(row["Year"]),
        "ERA": round(float(row["ERA"]), 2) if pd.notna(row["ERA"]) else None,
        "FIP": round(float(row["FIP"]), 2) if pd.notna(row["FIP"]) else None,
        "WHIP": round(float(row["WHIP"]), 2) if pd.notna(row["WHIP"]) else None,
        "WAR": round(float(row["WAR"]), 2) if pd.notna(row["WAR"]) else None,
        "GS": int(row["GS"]),
        "W": int(row["W"]),
        "L": int(row["L"]),
        "is_foreign": foreign,
        "is_rookie": rookie,
        "is_debut_foreign": debut_foreign,
        "prev_season": None,
    }

    # 올시즌 GS가 적으면 전년도 참고 스탯 추가
    if result["GS"] <= 3 and result["stats_year"] == year:
        prev = df[(df["Name"] == name) & (df["Year"] == year - 1)]
        if not prev.empty:
            pr = prev.iloc[0]
            result["prev_season"] = {
                "year": year - 1,
                "ERA": round(float(pr["ERA"]), 2) if pd.notna(pr["ERA"]) else None,
                "FIP": round(float(pr["FIP"]), 2) if pd.notna(pr["FIP"]) else None,
                "WAR": round(float(pr["WAR"]), 2) if pd.notna(pr["WAR"]) else None,
                "GS": int(pr["GS"]),
                "W": int(pr["W"]),
                "L": int(pr["L"]),
            }

    return result


def format_starter_info(info: dict | None, side: str) -> str:
    """조회 결과를 마크다운 텍스트로 포맷."""
    label = "원정" if side == "away" else "홈"

    if info is None:
        return f"**{label} 선발: 통계 미확인** (신규 등록 또는 이름 불일치)"

    lines = [f"**{label} 선발: {info['name']} ({info['team']})**"]

    # 메인 스탯
    year = info["stats_year"]
    era = f"ERA {info['ERA']}" if info["ERA"] is not None else "ERA -"
    fip = f"FIP {info['FIP']}" if info["FIP"] is not None else "FIP -"
    whip = f"WHIP {info['WHIP']}" if info["WHIP"] is not None else "WHIP -"
    war = f"WAR {info['WAR']}" if info["WAR"] is not None else "WAR -"
    lines.append(f"- {year} 시즌: {era}, {fip}, {whip}, {war}, "
                 f"{info['GS']}선발 {info['W']}승 {info['L']}패")

    # 전년도 참고
    if info["prev_season"]:
        ps = info["prev_season"]
        lines.append(f"- 참고({ps['year']}): ERA {ps['ERA']}, WAR {ps['WAR']}, "
                     f"{ps['GS']}선발 {ps['W']}승 {ps['L']}패")

    # 상태 플래그
    flags = []
    if info["is_debut_foreign"]:
        flags.append("외국인 선수 (KBO 데뷔 시즌 — 적응 불확실)")
    elif info["is_foreign"]:
        flags.append("외국인 선수")
    if info["is_rookie"]:
        flags.append("신인")

    if flags:
        lines.append(f"- 상태: {', '.join(flags)}")

    return "\n".join(lines)
