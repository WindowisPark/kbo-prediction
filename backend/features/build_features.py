"""
피처 엔지니어링 파이프라인 v2

개선점:
  1. 미래정보 누수 수정: 시즌 전체 스탯 → 전년도 스탯 사용
  2. 전년도 + 2년전 가중 블렌딩 (70/30) — 시즌 초반 안정성
  3. 홈/원정 분리 rolling stats (홈 경기만의 성적, 원정 경기만의 성적)
  4. 상대전적(head-to-head) 피처 추가
"""
import pandas as pd
import numpy as np
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent.parent))
from backend.utils.team_mapping import unify_team


def load_games(path: str | Path) -> pd.DataFrame:
    """경기 데이터 로드 및 전처리."""
    df = pd.read_csv(path)
    df["away_team"] = df["away_team"].apply(unify_team)
    df["home_team"] = df["home_team"].apply(unify_team)
    df["date"] = pd.to_datetime(df["date"], format="%Y.%m.%d")
    df = df.sort_values("date").reset_index(drop=True)

    df = df[df["home_score"] != df["away_score"]].copy()
    df["home_win"] = (df["home_score"] > df["away_score"]).astype(int)
    df["run_diff"] = df["home_score"] - df["away_score"]

    return df


def compute_rolling_stats(games: pd.DataFrame, windows: list[int] = [10, 20, 30]) -> pd.DataFrame:
    """팀별 rolling stats 계산 — vectorized."""

    records = []
    for _, row in games.iterrows():
        records.append({
            "date": row["date"], "team": row["home_team"],
            "win": row["home_win"], "runs_for": row["home_score"],
            "runs_against": row["away_score"], "game_idx": row.name,
            "is_home": 1,
        })
        records.append({
            "date": row["date"], "team": row["away_team"],
            "win": 1 - row["home_win"], "runs_for": row["away_score"],
            "runs_against": row["home_score"], "game_idx": row.name,
            "is_home": 0,
        })

    team_games = pd.DataFrame(records).sort_values(["team", "date"]).reset_index(drop=True)
    team_games["run_diff"] = team_games["runs_for"] - team_games["runs_against"]

    rolling_features = {}

    for team, grp in team_games.groupby("team"):
        grp = grp.reset_index(drop=True)
        for w in windows:
            win_pct = grp["win"].rolling(w, min_periods=max(w // 2, 1)).mean().shift(1)
            run_diff_r = grp["run_diff"].rolling(w, min_periods=max(w // 2, 1)).mean().shift(1)
            runs_for_r = grp["runs_for"].rolling(w, min_periods=max(w // 2, 1)).mean().shift(1)
            runs_against_r = grp["runs_against"].rolling(w, min_periods=max(w // 2, 1)).mean().shift(1)

            for i, (_, r) in enumerate(grp.iterrows()):
                key = (r["game_idx"], r["team"])
                if key not in rolling_features:
                    rolling_features[key] = {}
                rolling_features[key][f"win_pct_{w}"] = win_pct.iloc[i]
                rolling_features[key][f"run_diff_{w}"] = run_diff_r.iloc[i]
                rolling_features[key][f"runs_for_{w}"] = runs_for_r.iloc[i]
                rolling_features[key][f"runs_against_{w}"] = runs_against_r.iloc[i]

        # streak
        streak = 0
        for i, (_, r) in enumerate(grp.iterrows()):
            key = (r["game_idx"], r["team"])
            if key not in rolling_features:
                rolling_features[key] = {}
            rolling_features[key]["streak"] = streak
            if r["win"] == 1:
                streak = streak + 1 if streak > 0 else 1
            else:
                streak = streak - 1 if streak < 0 else -1

        # 홈/원정 분리 승률 (최근 20경기 중)
        home_mask = grp["is_home"] == 1
        away_mask = grp["is_home"] == 0
        home_grp = grp[home_mask].reset_index()
        away_grp = grp[away_mask].reset_index()

        home_win_pct = home_grp["win"].rolling(10, min_periods=3).mean().shift(1)
        away_win_pct = away_grp["win"].rolling(10, min_periods=3).mean().shift(1)

        for i, (_, r) in enumerate(home_grp.iterrows()):
            key = (r["game_idx"], r["team"])
            if key not in rolling_features:
                rolling_features[key] = {}
            rolling_features[key]["home_specific_win_pct"] = home_win_pct.iloc[i]

        for i, (_, r) in enumerate(away_grp.iterrows()):
            key = (r["game_idx"], r["team"])
            if key not in rolling_features:
                rolling_features[key] = {}
            rolling_features[key]["away_specific_win_pct"] = away_win_pct.iloc[i]

    # 경기 데이터에 결합
    feat_cols = []
    for w in windows:
        for prefix in ["home", "away"]:
            for stat in ["win_pct", "run_diff", "runs_for", "runs_against"]:
                col = f"{prefix}_{stat}_{w}"
                feat_cols.append(col)
                games[col] = np.nan

    for col in ["home_streak", "away_streak", "home_home_win_pct", "away_away_win_pct"]:
        games[col] = np.nan

    for idx in games.index:
        home = games.loc[idx, "home_team"]
        away = games.loc[idx, "away_team"]
        hf = rolling_features.get((idx, home), {})
        af = rolling_features.get((idx, away), {})

        for w in windows:
            for stat in ["win_pct", "run_diff", "runs_for", "runs_against"]:
                games.loc[idx, f"home_{stat}_{w}"] = hf.get(f"{stat}_{w}", np.nan)
                games.loc[idx, f"away_{stat}_{w}"] = af.get(f"{stat}_{w}", np.nan)

        games.loc[idx, "home_streak"] = hf.get("streak", 0)
        games.loc[idx, "away_streak"] = af.get("streak", 0)
        games.loc[idx, "home_home_win_pct"] = hf.get("home_specific_win_pct", np.nan)
        games.loc[idx, "away_away_win_pct"] = af.get("away_specific_win_pct", np.nan)

    return games


def compute_head_to_head(games: pd.DataFrame, window: int = 10) -> pd.DataFrame:
    """상대전적 피처 — 최근 N번의 맞대결 결과."""
    h2h_records = {}

    h2h_win_pct = []
    h2h_count = []

    for _, row in games.iterrows():
        home = row["home_team"]
        away = row["away_team"]
        matchup = tuple(sorted([home, away]))

        if matchup not in h2h_records:
            h2h_records[matchup] = []

        # 이전 맞대결에서 home팀의 승률
        past = h2h_records[matchup][-window:]
        if past:
            home_wins = sum(1 for r in past if r["winner"] == home)
            h2h_win_pct.append(home_wins / len(past))
            h2h_count.append(len(past))
        else:
            h2h_win_pct.append(np.nan)
            h2h_count.append(0)

        # 현재 결과 기록
        winner = home if row["home_win"] == 1 else away
        h2h_records[matchup].append({"winner": winner, "date": row["date"]})

    games["h2h_win_pct"] = h2h_win_pct
    games["h2h_count"] = h2h_count

    return games


def compute_elo(games: pd.DataFrame, k: int = 20, home_adv: float = 30) -> pd.DataFrame:
    """ELO 레이팅 계산."""
    elo = {}
    elo_history_home = []
    elo_history_away = []

    for _, row in games.iterrows():
        home = row["home_team"]
        away = row["away_team"]
        season = row["date"].year

        for team in [home, away]:
            if team not in elo:
                elo[team] = 1500
            key = f"{team}_last_season"
            if key not in elo:
                elo[key] = season
            if elo[key] != season:
                elo[team] = elo[team] * 0.7 + 1500 * 0.3
                elo[key] = season

        elo_history_home.append(elo[home])
        elo_history_away.append(elo[away])

        expected_home = 1 / (1 + 10 ** ((elo[away] - elo[home] - home_adv) / 400))
        actual_home = row["home_win"]
        margin = abs(row["run_diff"])
        elo_diff_winner = (elo[home] - elo[away]) if actual_home == 1 else (elo[away] - elo[home])
        margin_mult = np.log(margin + 1) * (2.2 / (elo_diff_winner * 0.001 + 2.2))

        update = k * margin_mult * (actual_home - expected_home)
        elo[home] += update
        elo[away] -= update

    games["home_elo"] = elo_history_home
    games["away_elo"] = elo_history_away
    games["elo_diff"] = games["home_elo"] - games["away_elo"]
    games["elo_expected"] = 1 / (1 + 10 ** (-(games["elo_diff"] + home_adv) / 400))

    return games


def add_temporal_features(games: pd.DataFrame) -> pd.DataFrame:
    """날짜 기반 피처."""
    games["month"] = games["date"].dt.month
    games["day_of_week"] = games["date"].dt.dayofweek
    games["is_weekend"] = games["day_of_week"].isin([5, 6]).astype(int)
    games["days_into_season"] = games.groupby("season")["date"].transform(
        lambda x: (x - x.min()).dt.days
    )
    return games


def add_prior_season_stats(games: pd.DataFrame, batting_path: str | Path, pitching_path: str | Path) -> pd.DataFrame:
    """
    전년도 시즌 스탯 기반 피처 (미래정보 누수 없음).

    전년도(70%) + 2년전(30%) 가중 블렌딩으로 안정성 확보.
    """
    bat = pd.read_csv(batting_path)
    pit = pd.read_csv(pitching_path)

    bat["Team"] = bat["Team"].apply(unify_team)
    pit["Team"] = pit["Team"].apply(unify_team)

    # 팀별 시즌 스탯 계산
    team_bat = bat.groupby(["Year", "Team"]).agg({
        "OPS": "mean", "OBP": "mean", "SLG": "mean",
        "HR": "sum", "WAR": "sum",
    }).reset_index()

    if "wRC+" in bat.columns:
        wrc = bat.groupby(["Year", "Team"])["wRC+"].mean().reset_index()
        team_bat = team_bat.merge(wrc, on=["Year", "Team"], how="left")

    pit["ERA"] = pd.to_numeric(pit["ERA"], errors="coerce")
    pit["FIP"] = pd.to_numeric(pit["FIP"], errors="coerce")
    pit["WHIP"] = pd.to_numeric(pit["WHIP"], errors="coerce")
    pit["WAR_pit"] = pd.to_numeric(pit["WAR"], errors="coerce")

    team_pit = pit.groupby(["Year", "Team"]).agg({
        "ERA": "mean", "FIP": "mean", "WHIP": "mean", "WAR_pit": "sum",
    }).reset_index()

    starters = pit[pit["GS"] >= 10].copy()
    sp_stats = starters.groupby(["Year", "Team"]).agg({
        "ERA": "mean", "FIP": "mean", "WHIP": "mean", "WAR_pit": "mean",
    }).reset_index()
    sp_stats.columns = ["Year", "Team", "sp_era", "sp_fip", "sp_whip", "sp_war"]

    # 전년도/2년전 스탯 블렌딩 함수
    def get_blended_stats(df, year, team, cols, w1=0.7, w2=0.3):
        prev1 = df[(df["Year"] == year - 1) & (df["Team"] == team)]
        prev2 = df[(df["Year"] == year - 2) & (df["Team"] == team)]

        if prev1.empty and prev2.empty:
            return {c: np.nan for c in cols}
        elif prev1.empty:
            return {c: prev2[c].values[0] for c in cols}
        elif prev2.empty:
            return {c: prev1[c].values[0] for c in cols}
        else:
            return {c: prev1[c].values[0] * w1 + prev2[c].values[0] * w2 for c in cols}

    bat_cols = ["OPS", "OBP", "SLG", "HR", "WAR"]
    pit_cols = ["ERA", "FIP", "WHIP", "WAR_pit"]
    sp_cols = ["sp_era", "sp_fip", "sp_whip", "sp_war"]

    # 각 경기에 전년도 기반 스탯 부여
    for side in ["home", "away"]:
        for col in bat_cols:
            games[f"{side}_{col.lower()}"] = np.nan
        for col in pit_cols:
            games[f"{side}_{col.lower()}"] = np.nan
        for col in sp_cols:
            games[f"{side}_{col}"] = np.nan
        if "wRC+" in team_bat.columns:
            games[f"{side}_wrc_plus"] = np.nan

    years = games["date"].dt.year
    teams_home = games["home_team"]
    teams_away = games["away_team"]

    # 연도-팀 조합별로 한번만 계산 (캐시)
    cache_bat = {}
    cache_pit = {}
    cache_sp = {}
    cache_wrc = {}

    for _, row in games.iterrows():
        year = row["date"].year
        for side, team_col in [("home", "home_team"), ("away", "away_team")]:
            team = row[team_col]
            cache_key = (year, team)

            if cache_key not in cache_bat:
                cache_bat[cache_key] = get_blended_stats(team_bat, year, team, bat_cols)
                cache_pit[cache_key] = get_blended_stats(team_pit, year, team, pit_cols)
                cache_sp[cache_key] = get_blended_stats(sp_stats, year, team, sp_cols)
                if "wRC+" in team_bat.columns:
                    cache_wrc[cache_key] = get_blended_stats(team_bat, year, team, ["wRC+"])

            for col in bat_cols:
                games.loc[row.name, f"{side}_{col.lower()}"] = cache_bat[cache_key][col]
            for col in pit_cols:
                games.loc[row.name, f"{side}_{col.lower()}"] = cache_pit[cache_key][col]
            for col in sp_cols:
                games.loc[row.name, f"{side}_{col}"] = cache_sp[cache_key][col]
            if "wRC+" in team_bat.columns:
                games.loc[row.name, f"{side}_wrc_plus"] = cache_wrc[cache_key]["wRC+"]

    return games


def compute_diff_features(games: pd.DataFrame) -> pd.DataFrame:
    """차이 피처 계산."""
    for w in [10, 20, 30]:
        games[f"win_pct_diff_{w}"] = games[f"home_win_pct_{w}"] - games[f"away_win_pct_{w}"]
        games[f"run_diff_diff_{w}"] = games[f"home_run_diff_{w}"] - games[f"away_run_diff_{w}"]

    if "home_ops" in games.columns:
        games["ops_diff"] = games["home_ops"] - games["away_ops"]
    if "home_era" in games.columns:
        games["era_diff"] = games["away_era"] - games["home_era"]
    if "home_sp_era" in games.columns:
        games["sp_era_diff"] = games["away_sp_era"] - games["home_sp_era"]
    if "home_sp_war" in games.columns:
        games["sp_war_diff"] = games["home_sp_war"] - games["away_sp_war"]
    if "home_war" in games.columns:
        games["bat_war_diff"] = games["home_war"] - games["away_war"]
    games["streak_diff"] = games["home_streak"] - games["away_streak"]

    # 홈/원정 분리 승률 차이
    if "home_home_win_pct" in games.columns:
        games["home_away_split_diff"] = (
            games["home_home_win_pct"].fillna(0.5) - games["away_away_win_pct"].fillna(0.5)
        )

    return games


def build_feature_matrix(
    games_path: str | Path,
    batting_path: str | Path,
    pitching_path: str | Path,
    output_path: str | Path,
) -> pd.DataFrame:
    """전체 피처 매트릭스를 빌드."""
    print("Loading games...")
    games = load_games(games_path)
    print(f"  {len(games)} games loaded (ties removed)")

    print("Computing rolling stats...")
    games = compute_rolling_stats(games)

    print("Computing head-to-head stats...")
    games = compute_head_to_head(games)

    print("Computing ELO ratings...")
    games = compute_elo(games)

    print("Adding temporal features...")
    games = add_temporal_features(games)

    print("Adding prior season team stats (no data leakage)...")
    games = add_prior_season_stats(games, batting_path, pitching_path)

    print("Computing diff features...")
    games = compute_diff_features(games)

    # 저장
    output_path = Path(output_path)
    output_path.parent.mkdir(parents=True, exist_ok=True)
    games.to_csv(output_path, index=False, encoding="utf-8-sig")
    print(f"\nFeature matrix saved: {output_path}")
    print(f"  Shape: {games.shape}")

    null_pct = (games.isnull().sum() / len(games) * 100).round(1)
    non_zero = null_pct[null_pct > 0]
    if len(non_zero) > 0:
        print(f"\n  Columns with nulls:")
        for col, pct in non_zero.items():
            print(f"    {col}: {pct}%")

    return games


if __name__ == "__main__":
    ROOT = Path(__file__).parent.parent.parent
    build_feature_matrix(
        games_path=ROOT / "data" / "raw" / "kbo_games_2000_2025.csv",
        batting_path=ROOT / "data" / "processed" / "batting_2000_2025.csv",
        pitching_path=ROOT / "data" / "processed" / "pitching_2000_2025.csv",
        output_path=ROOT / "data" / "features" / "game_features_v2.csv",
    )
