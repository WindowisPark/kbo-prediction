"""
KBO 공식 사이트(koreabaseball.com)에서 경기 데이터를 수집하는 스크래퍼.

수집 대상:
- 경기 일정 및 결과 (2000~2025)
- 날짜, 홈/원정 팀, 점수, game_id
"""
import requests
import pandas as pd
import re
import time
import logging
from pathlib import Path
from bs4 import BeautifulSoup

logging.basicConfig(level=logging.INFO, format="%(asctime)s [%(levelname)s] %(message)s")
logger = logging.getLogger(__name__)

BASE_URL = "https://www.koreabaseball.com"
SCHEDULE_API = f"{BASE_URL}/ws/Schedule.asmx/GetScheduleList"

HEADERS = {
    "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
                  "(KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36",
    "Referer": f"{BASE_URL}/Schedule/Schedule.aspx",
}


class KBOGameScraper:
    """KBO 공식 사이트에서 경기 결과를 수집."""

    def __init__(self, output_dir: str | Path = "data/raw"):
        self.output_dir = Path(output_dir)
        self.output_dir.mkdir(parents=True, exist_ok=True)
        self.session = requests.Session()
        self.session.headers.update(HEADERS)

    def scrape_month(self, year: int, month: int) -> list[dict]:
        """특정 연/월의 경기 결과를 가져온다."""
        payload = {
            "leId": "1",
            "srIdList": "0,9,6",
            "seasonId": str(year),
            "gameMonth": f"{month:02d}",
            "teamId": "",
        }

        try:
            resp = self.session.post(SCHEDULE_API, data=payload, timeout=15)
            resp.raise_for_status()
            data = resp.json()
        except (requests.RequestException, ValueError) as e:
            logger.warning(f"요청 실패 ({year}-{month:02d}): {e}")
            return []

        rows = data.get("rows", [])
        if not rows:
            return []

        games = []
        current_date = ""

        for row_obj in rows:
            cells = row_obj.get("row", [])

            # 날짜 셀 추출
            for cell in cells:
                cls = cell.get("Class") or ""
                if cls == "day":
                    date_match = re.search(r"(\d{2}\.\d{2})", cell.get("Text", ""))
                    if date_match:
                        current_date = date_match.group(1)

            # 경기 셀 추출
            play_text = ""
            review_text = ""
            stadium = ""

            for cell in cells:
                cls = cell.get("Class") or ""
                text = cell.get("Text") or ""
                if cls == "play":
                    play_text = text
                elif "etc" in cls.lower() or cls == "relay":
                    review_text = text
                elif cls == "field":
                    stadium = BeautifulSoup(text, "html.parser").get_text(strip=True)

            if not play_text:
                continue

            # 팀명, 점수 파싱
            soup = BeautifulSoup(play_text, "html.parser")
            teams = []
            scores = []

            for span in soup.find_all("span"):
                classes = span.get("class") or []
                text = span.get_text(strip=True)
                if not text or text == "vs":
                    continue
                if "win" in classes or "lose" in classes or "draw" in classes:
                    scores.append(text)
                elif not classes:
                    teams.append(text)

            # game_id 추출
            game_id = ""
            id_match = re.search(r"gameId=(\w+)", review_text)
            if id_match:
                game_id = id_match.group(1)

            if len(teams) >= 2 and len(scores) >= 2:
                games.append({
                    "game_id": game_id,
                    "date": f"{year}.{current_date}",
                    "away_team": teams[0],
                    "home_team": teams[-1],
                    "away_score": int(scores[0]),
                    "home_score": int(scores[1]),
                    "stadium": stadium,
                    "season": year,
                })

        logger.info(f"{year}-{month:02d}: {len(games)}경기 수집")
        return games

    def scrape_season(self, year: int) -> pd.DataFrame:
        """한 시즌 전체 경기를 수집."""
        all_games = []
        for month in range(3, 12):
            games = self.scrape_month(year, month)
            all_games.extend(games)
            time.sleep(1)

        df = pd.DataFrame(all_games)
        if not df.empty:
            output_path = self.output_dir / f"kbo_games_{year}.csv"
            df.to_csv(output_path, index=False, encoding="utf-8-sig")
            logger.info(f"{year} 시즌 저장: {output_path} ({len(df)}경기)")
        return df

    def scrape_range(self, start_year: int = 2000, end_year: int = 2025) -> pd.DataFrame:
        """여러 시즌 데이터를 일괄 수집."""
        all_dfs = []
        for year in range(start_year, end_year + 1):
            df = self.scrape_season(year)
            if not df.empty:
                all_dfs.append(df)
            time.sleep(2)

        if all_dfs:
            combined = pd.concat(all_dfs, ignore_index=True)
            output_path = self.output_dir / f"kbo_games_{start_year}_{end_year}.csv"
            combined.to_csv(output_path, index=False, encoding="utf-8-sig")
            logger.info(f"전체 저장: {output_path} ({len(combined)}경기)")
            return combined
        return pd.DataFrame()


def main():
    scraper = KBOGameScraper()
    df = scraper.scrape_range(2000, 2025)
    print(f"\n수집 완료: {len(df)}경기")
    print(df.head())


if __name__ == "__main__":
    main()
