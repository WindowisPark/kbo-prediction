"""
외국인 투수 유사도 매칭 모듈.

KBO 데뷔 시즌 외국인 투수에 대해 역대 유사 프로필 외국인 투수를 찾고,
그들의 KBO 적응 결과(성공/평균/부진)를 참조 정보로 반환한다.

매칭 전략:
- 시즌 초반(GS < 5): 나이 + 투구손 기반 프로필 매칭
- 시즌 중(GS >= 5): 초반 성적(ERA, FIP, WHIP, K/9, BB/9) 기반 매칭
"""

import pandas as pd
import numpy as np
from pathlib import Path
from typing import Optional


# KBO 적응 결과 분류 기준 (선발투수 GS >= 10 기준)
ERA_SUCCESS = 4.0    # 이하 → 성공
ERA_AVERAGE = 5.5    # 이하 → 평균
# 초과 → 부진


def _classify_adaptation(era: float, gs: int) -> str:
    """시즌 성적 기반 KBO 적응 결과 분류."""
    if gs < 10:
        return "소표본"
    if era <= ERA_SUCCESS:
        return "성공"
    elif era <= ERA_AVERAGE:
        return "평균"
    else:
        return "부진"


def _rate_stats(ip: float, so: int, bb: int, hr: int) -> dict:
    """이닝 기반 비율 스탯 계산 (K/9, BB/9, HR/9)."""
    if ip <= 0:
        return {"K9": 0.0, "BB9": 0.0, "HR9": 0.0}
    return {
        "K9": round(so * 9 / ip, 2),
        "BB9": round(bb * 9 / ip, 2),
        "HR9": round(hr * 9 / ip, 2),
    }


def build_foreign_pitcher_index(pitcher_df: pd.DataFrame) -> pd.DataFrame:
    """
    역대 외국인 투수 데뷔 시즌 데이터를 인덱스로 구축.

    Returns:
        DataFrame with columns: Name, Team, Year, Age, Handedness,
        ERA, FIP, WHIP, WAR, GS, IP, SO, BB, HR, K9, BB9, HR9, adaptation
    """
    foreign = pitcher_df[
        pitcher_df["Draft"].str.contains("외국인|자유선발", na=False)
    ].copy()

    if foreign.empty:
        return pd.DataFrame()

    # 데뷔 시즌 = 해당 선수의 첫 KBO 시즌
    debut_year = foreign.groupby("Name")["Year"].min().rename("debut_year")
    foreign = foreign.merge(debut_year, on="Name")
    first_season = foreign[foreign["Year"] == foreign["debut_year"]].copy()

    # 비율 스탯 계산
    ip_numeric = pd.to_numeric(first_season["IP"], errors="coerce").fillna(0)
    so_numeric = pd.to_numeric(first_season["SO"], errors="coerce").fillna(0)
    bb_numeric = pd.to_numeric(first_season["BB"], errors="coerce").fillna(0)
    hr_numeric = pd.to_numeric(first_season["HR"], errors="coerce").fillna(0)

    first_season["K9"] = np.where(
        ip_numeric > 0, (so_numeric * 9 / ip_numeric).round(2), 0.0
    )
    first_season["BB9"] = np.where(
        ip_numeric > 0, (bb_numeric * 9 / ip_numeric).round(2), 0.0
    )
    first_season["HR9"] = np.where(
        ip_numeric > 0, (hr_numeric * 9 / ip_numeric).round(2), 0.0
    )

    # 적응 결과 분류
    first_season["adaptation"] = first_season.apply(
        lambda r: _classify_adaptation(r["ERA"], r["GS"]), axis=1
    )

    cols = [
        "Name", "Team", "Year", "Age", "Handedness",
        "ERA", "FIP", "WHIP", "WAR", "GS", "IP", "SO", "BB", "HR",
        "K9", "BB9", "HR9", "adaptation",
    ]
    return first_season[cols].reset_index(drop=True)


def find_similar_pitchers(
    target: dict,
    index_df: pd.DataFrame,
    k: int = 5,
    min_gs: int = 10,
) -> list[dict]:
    """
    타깃 외국인 투수와 유사한 역대 외국인 투수를 찾는다.

    Args:
        target: lookup_starter 반환값 (player_stats.py)
        index_df: build_foreign_pitcher_index 결과
        k: 반환할 유사 선수 수
        min_gs: 비교 대상 최소 선발 경기 수

    Returns:
        [{name, team, year, age, era, fip, war, adaptation, similarity, distance}, ...]
    """
    if index_df.empty or target is None:
        return []

    # 본인 제외 + 최소 GS 필터
    candidates = index_df[
        (index_df["Name"] != target["name"]) & (index_df["GS"] >= min_gs)
    ].copy()

    if candidates.empty:
        return []

    target_gs = target.get("GS", 0)
    target_era = target.get("ERA")
    target_fip = target.get("FIP")
    target_age = None

    # pitcher_df에서 나이 정보 가져오기 (target에 없을 수 있음)
    # target에 age가 있으면 사용
    if "age" in target:
        target_age = target["age"]
    elif "Age" in target:
        target_age = target["Age"]

    # 매칭 전략 분기
    if target_gs >= 5 and target_era is not None and target_fip is not None:
        # 성적 기반 매칭: ERA, FIP, WHIP 유사도
        return _match_by_stats(target, candidates, k)
    else:
        # 프로필 기반 매칭: 나이 + 투구손
        return _match_by_profile(target, candidates, k)


def _match_by_stats(target: dict, candidates: pd.DataFrame, k: int) -> list[dict]:
    """성적 기반 유사도 매칭 (코사인 유사도 대신 유클리드 거리 — 해석 용이)."""
    features = ["ERA", "FIP", "WHIP", "K9", "BB9"]

    # 타깃 피처 벡터
    target_ip = float(target.get("IP", 0)) if target.get("IP") else 0
    target_so = int(target.get("SO", 0)) if target.get("SO") else 0
    target_bb = int(target.get("BB", 0)) if target.get("BB") else 0
    rates = _rate_stats(target_ip, target_so, target_bb, 0)

    target_vec = np.array([
        target.get("ERA", 4.5),
        target.get("FIP", 4.5),
        target.get("WHIP", 1.4),
        rates["K9"],
        rates["BB9"],
    ], dtype=float)

    # 후보 피처 매트릭스
    cand_matrix = candidates[features].values.astype(float)

    # 스케일링 (각 피처를 후보 데이터의 std로 나눠서 단위 차이 보정)
    stds = np.std(cand_matrix, axis=0)
    stds[stds == 0] = 1.0
    scaled_target = target_vec / stds
    scaled_cand = cand_matrix / stds

    # 유클리드 거리 계산
    distances = np.sqrt(np.sum((scaled_cand - scaled_target) ** 2, axis=1))
    candidates = candidates.copy()
    candidates["distance"] = distances

    top_k = candidates.nsmallest(k, "distance")
    return _format_results(top_k)


def _match_by_profile(target: dict, candidates: pd.DataFrame, k: int) -> list[dict]:
    """프로필 기반 매칭 (시즌 초반, 성적 미축적 시)."""
    candidates = candidates.copy()

    # 나이 차이 (가장 중요한 피처)
    target_age = target.get("age") or target.get("Age") or 29  # 평균값 fallback
    candidates["age_diff"] = (candidates["Age"] - target_age).abs()

    # 투구손 일치 보너스 (같으면 0, 다르면 1)
    target_hand = target.get("Handedness", "")
    candidates["hand_penalty"] = candidates["Handedness"].apply(
        lambda h: 0 if h == target_hand else 1
    )

    # 종합 거리: 나이 차이 + 투구손 패널티 * 3
    candidates["distance"] = candidates["age_diff"] + candidates["hand_penalty"] * 3

    top_k = candidates.nsmallest(k, "distance")
    return _format_results(top_k)


def _format_results(df: pd.DataFrame) -> list[dict]:
    """결과를 딕셔너리 리스트로 포맷."""
    results = []
    for _, row in df.iterrows():
        results.append({
            "name": row["Name"],
            "team": row["Team"],
            "year": int(row["Year"]),
            "age": int(row["Age"]),
            "era": round(float(row["ERA"]), 2),
            "fip": round(float(row["FIP"]), 2),
            "war": round(float(row["WAR"]), 2),
            "gs": int(row["GS"]),
            "adaptation": row["adaptation"],
            "distance": round(float(row["distance"]), 3),
        })
    return results


def format_similar_pitchers_context(
    target_name: str,
    similar: list[dict],
) -> str:
    """유사 외국인 투수 매칭 결과를 에이전트 컨텍스트 텍스트로 포맷."""
    if not similar:
        return ""

    lines = [f"**{target_name} 유사 외국인 투수 (역대 KBO 데뷔 시즌 기준)**"]

    # 적응 결과 요약
    adaptations = [s["adaptation"] for s in similar]
    success = adaptations.count("성공")
    average = adaptations.count("평균")
    fail = adaptations.count("부진")
    lines.append(f"- 유사 유형 {len(similar)}명 중: 성공 {success}, 평균 {average}, 부진 {fail}")

    # 개별 선수 목록
    for s in similar:
        icon = {"성공": "+", "평균": "~", "부진": "-"}.get(s["adaptation"], "?")
        lines.append(
            f"  [{icon}] {s['name']}({s['team']}, {s['year']}) "
            f"— {s['age']}세, ERA {s['era']}, FIP {s['fip']}, "
            f"WAR {s['war']}, {s['gs']}선발 → {s['adaptation']}"
        )

    # 해석 가이드
    avg_era = np.mean([s["era"] for s in similar])
    lines.append(f"- 유사 유형 평균 데뷔 시즌 ERA: {avg_era:.2f}")

    return "\n".join(lines)
