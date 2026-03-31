"""
KBO 경기별 라인업을 박스스코어에서 추출.

BoxScore API 응답 구조:
  Table 0: 경기 요약 (결승타, 2루타, 실책 등)
  Table 1: 원정팀 타자 라인업 (타순, 포지션, 이름, 이닝별 결과)
  Table 2: 홈팀 타자 라인업
  Table 3: 원정팀 투수진
  Table 4: 홈팀 투수진
"""
import requests
from bs4 import BeautifulSoup


BASE_URL = "https://www.koreabaseball.com"
HEADERS = {
    "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36",
    "Referer": f"{BASE_URL}/Schedule/GameCenter/Main.aspx",
}


def get_lineup(game_id: str) -> dict | None:
    """
    경기 박스스코어에서 라인업을 추출.

    Returns:
        {
            "away_lineup": [{"order": 1, "position": "중", "name": "홍길동"}, ...],
            "home_lineup": [...],
            "away_pitchers": [{"name": "...", "role": "선발", ...}, ...],
            "home_pitchers": [...],
            "away_starter": "투수이름",
            "home_starter": "투수이름",
        }
    """
    session = requests.Session()
    session.headers.update(HEADERS)

    season = game_id[:4]
    resp = session.post(
        f"{BASE_URL}/ws/Schedule.asmx/GetBoxScore",
        data={"gameId": game_id, "leId": "1", "srId": "0", "seasonId": season},
        timeout=15,
    )

    if resp.status_code != 200:
        return None

    data = resp.json()
    tables = data.get("tables", [])

    if len(tables) < 5:
        return None

    def parse_batters(table) -> list[dict]:
        lineup = []
        for row in table.get("rows", []):
            cells = row.get("row", [])
            if len(cells) < 3:
                continue
            order = BeautifulSoup(cells[0].get("Text", ""), "html.parser").get_text(strip=True)
            pos = BeautifulSoup(cells[1].get("Text", ""), "html.parser").get_text(strip=True)
            name = BeautifulSoup(cells[2].get("Text", ""), "html.parser").get_text(strip=True)
            if order and name:
                lineup.append({"order": order, "position": pos, "name": name})
        return lineup

    def parse_pitchers(table) -> list[dict]:
        pitchers = []
        for row in table.get("rows", []):
            cells = row.get("row", [])
            if len(cells) < 2:
                continue
            name = BeautifulSoup(cells[0].get("Text", ""), "html.parser").get_text(strip=True)
            role = BeautifulSoup(cells[1].get("Text", ""), "html.parser").get_text(strip=True)
            if name and not name.isdigit():
                pitchers.append({"name": name, "role": role})
            elif name.isdigit():
                pitchers.append({"name": f"ID_{name}", "role": role})
        return pitchers

    away_lineup = parse_batters(tables[1])
    home_lineup = parse_batters(tables[2])
    away_pitchers = parse_pitchers(tables[3])
    home_pitchers = parse_pitchers(tables[4])

    away_starter = ""
    home_starter = ""
    for p in away_pitchers:
        if p["role"] == "선발":
            away_starter = p["name"]
            break
    for p in home_pitchers:
        if p["role"] == "선발":
            home_starter = p["name"]
            break

    return {
        "away_lineup": away_lineup,
        "home_lineup": home_lineup,
        "away_pitchers": away_pitchers,
        "home_pitchers": home_pitchers,
        "away_starter": away_starter,
        "home_starter": home_starter,
    }


if __name__ == "__main__":
    import sys
    sys.stdout.reconfigure(encoding="utf-8")

    result = get_lineup("20240402LTHH0")
    if result:
        print(f"Away starter: {result['away_starter']}")
        print(f"Home starter: {result['home_starter']}")
        print(f"\nAway lineup ({len(result['away_lineup'])} batters):")
        for b in result["away_lineup"]:
            print(f"  {b['order']}. {b['position']:3s} {b['name']}")
        print(f"\nHome lineup ({len(result['home_lineup'])} batters):")
        for b in result["home_lineup"]:
            print(f"  {b['order']}. {b['position']:3s} {b['name']}")
