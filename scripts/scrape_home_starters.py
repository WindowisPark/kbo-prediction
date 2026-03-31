"""
GetKboGameList API로 홈/원정 선발투수를 빠르게 수집.
날짜 단위 호출이라 경기 단위보다 훨씬 빠름.
"""
import requests
import pandas as pd
import time
import logging
import sys
from pathlib import Path

sys.stdout.reconfigure(encoding="utf-8")
logging.basicConfig(level=logging.INFO, format="%(asctime)s [%(levelname)s] %(message)s")
logger = logging.getLogger(__name__)

ROOT = Path(__file__).parent.parent
BASE_URL = "https://www.koreabaseball.com"
HEADERS = {
    "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36",
    "Referer": BASE_URL,
}


def main():
    games = pd.read_csv(ROOT / "data" / "raw" / "kbo_games_2000_2025.csv")
    unique_dates = sorted(games["game_id"].str[:8].unique())
    logger.info(f"Unique dates: {len(unique_dates)}")

    session = requests.Session()
    session.headers.update(HEADERS)

    output_path = ROOT / "data" / "raw" / "kbo_starters_full.csv"

    # 이어하기
    if output_path.exists():
        existing = pd.read_csv(output_path)
        done_dates = set(existing["game_id"].str[:8].unique())
        results = existing.to_dict("records")
        logger.info(f"Resuming: {len(done_dates)} dates done")
    else:
        done_dates = set()
        results = []

    pending = [d for d in unique_dates if d not in done_dates]
    logger.info(f"Remaining: {len(pending)} dates")

    for i, date_str in enumerate(pending):
        resp = session.post(
            f"{BASE_URL}/ws/Main.asmx/GetKboGameList",
            data={"leId": "1", "srId": "0,9", "date": date_str},
            timeout=15,
        )

        try:
            data = resp.json()
            game_list = data.get("game", data.get("d", []))
            if isinstance(game_list, str):
                import json
                game_list = json.loads(game_list)
        except Exception:
            game_list = []

        for g in game_list:
            results.append({
                "game_id": g.get("G_ID", ""),
                "away_starter": (g.get("T_PIT_P_NM") or "").strip(),
                "home_starter": (g.get("B_PIT_P_NM") or "").strip(),
                "stadium": g.get("S_NM", ""),
            })

        if (i + 1) % 100 == 0:
            pd.DataFrame(results).to_csv(output_path, index=False, encoding="utf-8-sig")
            logger.info(f"Progress: {i+1}/{len(pending)} ({(i+1)/len(pending)*100:.1f}%)")

        time.sleep(0.3)

    result_df = pd.DataFrame(results)
    result_df.to_csv(output_path, index=False, encoding="utf-8-sig")

    found = result_df[(result_df["away_starter"] != "") & (result_df["home_starter"] != "")].shape[0]
    logger.info(f"Complete: {len(result_df)} games, starters found: {found} ({found/len(result_df)*100:.1f}%)")


if __name__ == "__main__":
    main()
