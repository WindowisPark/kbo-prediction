"""
KBO 경기별 선발투수 정보를 박스스코어에서 추출.

BoxScore API에서 투수 테이블을 파싱하여
각 경기의 원정/홈 선발투수를 식별한다.
"""
import requests
import pandas as pd
import time
import logging
import sys
from pathlib import Path
from bs4 import BeautifulSoup

logging.basicConfig(level=logging.INFO, format="%(asctime)s [%(levelname)s] %(message)s")
logger = logging.getLogger(__name__)

BASE_URL = "https://www.koreabaseball.com"
BOXSCORE_URL = f"{BASE_URL}/ws/Schedule.asmx/GetBoxScore"

HEADERS = {
    "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
                  "(KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36",
    "Referer": f"{BASE_URL}/Schedule/GameCenter/Main.aspx",
}


def extract_starters(game_id: str, session: requests.Session) -> dict | None:
    """박스스코어에서 원정/홈 선발투수 이름을 추출."""
    season = game_id[:4]
    payload = {
        "gameId": game_id,
        "leId": "1",
        "srId": "0",
        "seasonId": season,
    }

    try:
        resp = session.post(BOXSCORE_URL, data=payload, timeout=15)
        resp.raise_for_status()
        data = resp.json()
    except Exception:
        return None

    tables = data.get("tables", [])
    if len(tables) < 4:
        return None

    # 투수 테이블: 보통 table[3]=원정, table[4]=홈
    # "선발" 텍스트가 있는 첫 번째 행의 첫 셀이 선발투수 이름
    starters = {}
    pitcher_tables = []

    for table in tables:
        rows = table.get("rows", [])
        for row in rows:
            cells = row.get("row", [])
            cell_texts = [c.get("Text", "") for c in cells]
            if "선발" in cell_texts:
                pitcher_tables.append(table)
                break

    if len(pitcher_tables) >= 2:
        for idx, label in enumerate(["away_starter", "home_starter"]):
            table = pitcher_tables[idx]
            rows = table.get("rows", [])
            for row in rows:
                cells = row.get("row", [])
                cell_texts = [c.get("Text", "") for c in cells]
                if "선발" in cell_texts:
                    name_text = cell_texts[0]
                    name = BeautifulSoup(name_text, "html.parser").get_text(strip=True)
                    # 숫자만인 경우 (선수 ID가 나올 때) 건너뛰기
                    if name and not name.isdigit():
                        starters[label] = name
                    elif name.isdigit():
                        starters[label] = f"ID_{name}"
                    break

    if len(starters) == 2:
        return starters
    return None


def scrape_starters_for_games(games_csv: str | Path, output_csv: str | Path,
                               start_idx: int = 0, batch_size: int = 100):
    """경기 목록에서 선발투수를 일괄 추출."""
    df = pd.read_csv(games_csv)
    logger.info(f"Total games: {len(df)}")

    session = requests.Session()
    session.headers.update(HEADERS)

    output_path = Path(output_csv)

    # 기존 결과 로드 (이어하기)
    if output_path.exists():
        existing = pd.read_csv(output_path)
        done_ids = set(existing["game_id"].values)
        results = existing.to_dict("records")
        logger.info(f"Resuming: {len(done_ids)} already done")
    else:
        done_ids = set()
        results = []

    pending = df[~df["game_id"].isin(done_ids)]
    logger.info(f"Remaining: {len(pending)} games")

    count = 0
    for _, row in pending.iterrows():
        game_id = row["game_id"]
        starters = extract_starters(game_id, session)

        if starters:
            results.append({
                "game_id": game_id,
                "away_starter": starters.get("away_starter", ""),
                "home_starter": starters.get("home_starter", ""),
            })
        else:
            results.append({
                "game_id": game_id,
                "away_starter": "",
                "home_starter": "",
            })

        count += 1
        if count % 50 == 0:
            # 중간 저장
            pd.DataFrame(results).to_csv(output_path, index=False, encoding="utf-8-sig")
            logger.info(f"Progress: {count}/{len(pending)} ({count/len(pending)*100:.1f}%)")

        time.sleep(0.5)  # 서버 부하 방지

    # 최종 저장
    result_df = pd.DataFrame(results)
    result_df.to_csv(output_path, index=False, encoding="utf-8-sig")
    logger.info(f"Complete: {len(result_df)} games saved to {output_path}")

    # 성공률
    found = result_df[result_df["away_starter"] != ""].shape[0]
    logger.info(f"Starters found: {found}/{len(result_df)} ({found/len(result_df)*100:.1f}%)")

    return result_df


if __name__ == "__main__":
    ROOT = Path(__file__).parent.parent.parent
    scrape_starters_for_games(
        games_csv=ROOT / "data" / "raw" / "kbo_games_2000_2025.csv",
        output_csv=ROOT / "data" / "raw" / "kbo_starters.csv",
    )
