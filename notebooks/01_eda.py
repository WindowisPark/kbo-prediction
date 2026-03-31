"""
KBO 데이터 탐색적 분석 (EDA)
- 2000~2025 선수/팀 스탯 분포
- 시즌별 트렌드
- 예측 모델에 쓸 피처 후보 탐색
"""
import pandas as pd
import numpy as np
from pathlib import Path

DATA_DIR = Path(__file__).parent.parent / "data" / "processed"

# === 데이터 로드 ===
bat = pd.read_csv(DATA_DIR / "batting_2000_2025.csv")
pit = pd.read_csv(DATA_DIR / "pitching_2000_2025.csv")

print(f"타격 데이터: {bat.shape}, 투구 데이터: {pit.shape}")
print(f"시즌 범위: {bat['Year'].min()}~{bat['Year'].max()}")

# === 팀명 통합 매핑 ===
TEAM_UNIFY = {
    "해태": "KIA", "현대": "Heroes", "우리": "Heroes",
    "넥센": "Heroes", "키움": "Heroes",
    "SK": "SSG",
}

bat["team_unified"] = bat["Team"].map(lambda t: TEAM_UNIFY.get(t, t))
pit["team_unified"] = pit["Team"].map(lambda t: TEAM_UNIFY.get(t, t))

# === 1. 시즌별 리그 평균 트렌드 ===
print("\n" + "=" * 60)
print("1. 시즌별 리그 평균 (규정타석 400+ 타자)")
print("=" * 60)

qualified_bat = bat[bat["PA"] >= 400]
season_avg = qualified_bat.groupby("Year").agg({
    "AVG": "mean", "OBP": "mean", "SLG": "mean",
    "OPS": "mean", "HR": "mean", "WAR": "mean",
}).round(3)
print(season_avg.tail(10))

# === 2. 투수 트렌드 ===
print("\n" + "=" * 60)
print("2. 시즌별 선발투수 평균 (GS >= 15)")
print("=" * 60)

starters = pit[pit["GS"] >= 15].copy()
starters["ERA"] = pd.to_numeric(starters["ERA"], errors="coerce")
starters["FIP"] = pd.to_numeric(starters["FIP"], errors="coerce")
starters["WHIP"] = pd.to_numeric(starters["WHIP"], errors="coerce")
starters["WAR"] = pd.to_numeric(starters["WAR"], errors="coerce")

season_pit = starters.groupby("Year").agg({
    "ERA": "mean", "FIP": "mean", "WHIP": "mean", "WAR": "mean",
}).round(3)
print(season_pit.tail(10))

# === 3. 팀별 WAR 합산 (공격/수비 밸런스) ===
print("\n" + "=" * 60)
print("3. 2024 팀별 타자 WAR 합산 (상위)")
print("=" * 60)

bat_2024 = bat[bat["Year"] == 2024]
team_war = bat_2024.groupby("team_unified")["WAR"].sum().sort_values(ascending=False)
print(team_war.to_string())

# === 4. 선발투수 중요도 분석 ===
print("\n" + "=" * 60)
print("4. 선발투수 WAR 분포 (2024, GS >= 15)")
print("=" * 60)

sp_2024 = starters[starters["Year"] == 2024].copy()
sp_2024 = sp_2024.sort_values("WAR", ascending=False)
print(sp_2024[["Name", "Team", "W", "L", "ERA", "FIP", "WAR"]].head(15).to_string())

# === 5. 팀 간 전력 편차 (예측 가능성 지표) ===
print("\n" + "=" * 60)
print("5. 시즌별 팀 WAR 표준편차 (팀간 격차)")
print("=" * 60)

team_season_war = bat.groupby(["Year", "team_unified"])["WAR"].sum().reset_index()
war_std = team_season_war.groupby("Year")["WAR"].std().round(2)
print(war_std.tail(10))
print(f"\n평균 팀간 WAR 편차: {war_std.mean():.2f}")
print("(편차가 클수록 예측이 쉬움)")

# === 6. 피처 후보 상관관계 ===
print("\n" + "=" * 60)
print("6. 타자 피처 간 상관관계 (규정타석)")
print("=" * 60)

corr_cols = ["AVG", "OBP", "SLG", "OPS", "HR", "WAR", "wRC+"]
corr = qualified_bat[corr_cols].corr().round(2)
print(corr)
