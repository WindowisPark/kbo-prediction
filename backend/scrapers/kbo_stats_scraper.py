"""
KBO 공식 사이트에서 선수 시즌 스탯을 수집하는 스크래퍼.

수집 대상:
- 타자 기본/어드밴스드 스탯 (2000~2025)
- 투수 기본/어드밴스드 스탯 (2000~2025)
- 팀 기록
"""
import requests
import pandas as pd
import time
import logging
from pathlib import Path
from bs4 import BeautifulSoup

logging.basicConfig(level=logging.INFO, format="%(asctime)s [%(levelname)s] %(message)s")
logger = logging.getLogger(__name__)

BASE_URL = "https://www.koreabaseball.com"

HEADERS = {
    "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
                  "(KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36",
    "Referer": BASE_URL,
}

# 타자 스탯 페이지
HITTER_URLS = {
    "basic": "/Record/Player/HitterBasic/Basic1.aspx",
    "advanced": "/Record/Player/HitterBasic/Basic2.aspx",
}

# 투수 스탯 페이지
PITCHER_URLS = {
    "basic": "/Record/Player/PitcherBasic/Basic1.aspx",
    "advanced": "/Record/Player/PitcherBasic/Basic2.aspx",
}

# 팀 스탯 페이지
TEAM_URLS = {
    "hitter": "/Record/Team/Hitter/Basic1.aspx",
    "pitcher": "/Record/Team/Pitcher/Basic1.aspx",
}


class KBOStatsScraper:
    """KBO 공식 사이트에서 시즌 스탯을 수집."""

    def __init__(self, output_dir: str | Path = "data/raw"):
        self.output_dir = Path(output_dir)
        self.output_dir.mkdir(parents=True, exist_ok=True)
        self.session = requests.Session()
        self.session.headers.update(HEADERS)

    def _parse_table(self, html: str) -> pd.DataFrame:
        """HTML 테이블을 DataFrame으로 변환."""
        soup = BeautifulSoup(html, "html.parser")
        table = soup.select_one("table.tData, table.style1, #cphContents_cphContents_cphContents_udpContent table")
        if not table:
            tables = soup.find_all("table")
            table = max(tables, key=lambda t: len(t.find_all("tr")), default=None) if tables else None

        if not table:
            return pd.DataFrame()

        # 헤더
        headers = []
        thead = table.find("thead")
        if thead:
            ths = thead.find_all("th")
            headers = [th.get_text(strip=True) for th in ths]

        # 바디
        rows = []
        tbody = table.find("tbody") or table
        for tr in tbody.find_all("tr"):
            tds = tr.find_all(["td", "th"])
            row = [td.get_text(strip=True) for td in tds]
            if row and len(row) > 1:
                rows.append(row)

        if not headers and rows:
            headers = [f"col_{i}" for i in range(len(rows[0]))]

        if not rows:
            return pd.DataFrame()

        # 열 수 맞추기
        max_cols = max(len(headers), max(len(r) for r in rows))
        headers = headers + [f"col_{i}" for i in range(len(headers), max_cols)]
        rows = [r + [""] * (max_cols - len(r)) for r in rows]

        return pd.DataFrame(rows, columns=headers[:max_cols])

    def _fetch_stats_page(self, path: str, year: int, page: int = 1) -> str:
        """ASP.NET 페이지에서 데이터를 가져온다."""
        url = f"{BASE_URL}{path}"
        params = {"year": str(year), "page": str(page)}

        try:
            resp = self.session.get(url, params=params, timeout=15)
            resp.raise_for_status()
            return resp.text
        except requests.RequestException as e:
            logger.warning(f"요청 실패 ({path}, {year}): {e}")
            return ""

    def scrape_hitter_stats(self, year: int) -> pd.DataFrame:
        """시즌 타자 스탯을 수집."""
        all_rows = []
        for stat_type, path in HITTER_URLS.items():
            page = 1
            while True:
                html = self._fetch_stats_page(path, year, page)
                if not html:
                    break

                df = self._parse_table(html)
                if df.empty:
                    break

                df["stat_type"] = stat_type
                all_rows.append(df)

                # 다음 페이지 확인
                soup = BeautifulSoup(html, "html.parser")
                next_btn = soup.select_one("a.next, .paging a:last-child")
                if not next_btn or page >= 10:
                    break
                page += 1
                time.sleep(0.5)

            time.sleep(1)

        if all_rows:
            combined = pd.concat(all_rows, ignore_index=True)
            combined["season"] = year
            output_path = self.output_dir / f"kbo_hitters_{year}.csv"
            combined.to_csv(output_path, index=False, encoding="utf-8-sig")
            logger.info(f"타자 스탯 저장: {output_path}")
            return combined
        return pd.DataFrame()

    def scrape_pitcher_stats(self, year: int) -> pd.DataFrame:
        """시즌 투수 스탯을 수집."""
        all_rows = []
        for stat_type, path in PITCHER_URLS.items():
            page = 1
            while True:
                html = self._fetch_stats_page(path, year, page)
                if not html:
                    break

                df = self._parse_table(html)
                if df.empty:
                    break

                df["stat_type"] = stat_type
                all_rows.append(df)

                soup = BeautifulSoup(html, "html.parser")
                next_btn = soup.select_one("a.next, .paging a:last-child")
                if not next_btn or page >= 10:
                    break
                page += 1
                time.sleep(0.5)

            time.sleep(1)

        if all_rows:
            combined = pd.concat(all_rows, ignore_index=True)
            combined["season"] = year
            output_path = self.output_dir / f"kbo_pitchers_{year}.csv"
            combined.to_csv(output_path, index=False, encoding="utf-8-sig")
            logger.info(f"투수 스탯 저장: {output_path}")
            return combined
        return pd.DataFrame()

    def scrape_team_stats(self, year: int) -> dict[str, pd.DataFrame]:
        """시즌 팀 스탯을 수집."""
        results = {}
        for stat_type, path in TEAM_URLS.items():
            html = self._fetch_stats_page(path, year)
            if html:
                df = self._parse_table(html)
                if not df.empty:
                    df["season"] = year
                    output_path = self.output_dir / f"kbo_team_{stat_type}_{year}.csv"
                    df.to_csv(output_path, index=False, encoding="utf-8-sig")
                    results[stat_type] = df
                    logger.info(f"팀 {stat_type} 스탯 저장: {output_path}")
            time.sleep(1)
        return results

    def scrape_range(self, start_year: int = 2000, end_year: int = 2025):
        """여러 시즌 선수/팀 스탯을 일괄 수집."""
        for year in range(start_year, end_year + 1):
            logger.info(f"=== {year} 시즌 스탯 수집 시작 ===")
            self.scrape_hitter_stats(year)
            self.scrape_pitcher_stats(year)
            self.scrape_team_stats(year)
            time.sleep(3)


def main():
    scraper = KBOStatsScraper()
    scraper.scrape_range(2000, 2025)
    print("스탯 수집 완료")


if __name__ == "__main__":
    main()
