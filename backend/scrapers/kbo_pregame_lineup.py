"""
경기 전 라인업 수집 — KBO GetLineUpAnalysis API.

경기 ~1.5시간 전 라인업 공개 시 확정 타선(1~9번) + 포지션 + WAR 반환.
LINEUP_CK=false면 미공개 상태.

사용법:
  lineup = get_pregame_lineup("20260401HTLG0")
  if lineup and lineup["available"]:
      print(lineup["home_lineup"])  # [{"order": "1", "position": "우익수", "name": "홍창기", "war": "0.00"}, ...]
"""
import json
import logging

import requests

logger = logging.getLogger(__name__)

BASE_URL = "https://www.koreabaseball.com"
HEADERS = {
    "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36",
    "Referer": f"{BASE_URL}/Schedule/GameCenter/Preview/LineUp.aspx",
}


def _parse_lineup_table(table_json_str: str) -> list[dict]:
    """라인업 테이블 JSON 문자열 → [{order, position, name, war}, ...]"""
    try:
        table = json.loads(table_json_str)
    except (json.JSONDecodeError, TypeError):
        return []

    lineup = []
    for row in table.get("rows", []):
        cells = row.get("row", [])
        if len(cells) < 3:
            continue
        order = (cells[0].get("Text") or "").strip()
        position = (cells[1].get("Text") or "").strip()
        name = (cells[2].get("Text") or "").strip()
        war = (cells[3].get("Text") or "").strip() if len(cells) > 3 else ""

        if order and name:
            lineup.append({
                "order": order,
                "position": position,
                "name": name,
                "war": war,
            })
    return lineup


def get_pregame_lineup(game_id: str) -> dict | None:
    """
    경기 전 확정 라인업 조회.

    Returns:
        {
            "available": bool,
            "home_team": str,
            "away_team": str,
            "home_lineup": [{"order", "position", "name", "war"}, ...],
            "away_lineup": [...],
        }
        또는 API 실패 시 None
    """
    session = requests.Session()
    session.headers.update(HEADERS)

    season = game_id[:4]
    try:
        resp = session.post(
            f"{BASE_URL}/ws/Schedule.asmx/GetLineUpAnalysis",
            data={"gameId": game_id, "leId": "1", "srId": "0", "seasonId": season},
            timeout=15,
        )
    except Exception as e:
        logger.error(f"GetLineUpAnalysis failed for {game_id}: {e}")
        return None

    if resp.status_code != 200:
        return None

    try:
        data = resp.json()
    except Exception:
        return None

    if not isinstance(data, list) or len(data) < 5:
        return None

    # [0] 라인업 공개 여부
    lineup_ck = False
    if data[0] and isinstance(data[0], list) and data[0]:
        lineup_ck = data[0][0].get("LINEUP_CK", False)

    # [1] 홈팀 정보, [2] 원정팀 정보
    home_team = ""
    away_team = ""
    if data[1] and isinstance(data[1], list) and data[1]:
        home_team = data[1][0].get("T_NM", "")
    if data[2] and isinstance(data[2], list) and data[2]:
        away_team = data[2][0].get("T_NM", "")

    # [3] 홈팀 라인업, [4] 원정팀 라인업 (JSON 문자열)
    home_lineup = []
    away_lineup = []
    if lineup_ck:
        if data[3] and isinstance(data[3], list) and data[3]:
            home_lineup = _parse_lineup_table(data[3][0] if isinstance(data[3][0], str) else "")
        if data[4] and isinstance(data[4], list) and data[4]:
            away_lineup = _parse_lineup_table(data[4][0] if isinstance(data[4][0], str) else "")

    return {
        "available": bool(lineup_ck),
        "home_team": home_team,
        "away_team": away_team,
        "home_lineup": home_lineup,
        "away_lineup": away_lineup,
    }


def format_lineup_context(lineup_data: dict) -> str:
    """라인업 데이터를 LLM 맥락 문자열로 변환."""
    if not lineup_data or not lineup_data.get("available"):
        return ""

    lines = []
    for side, key in [("홈", "home_lineup"), ("원정", "away_lineup")]:
        players = lineup_data.get(key, [])
        if not players:
            continue
        lines.append(f"\n### {side} 타선 (확정)")
        for p in players[:9]:
            war_str = f" (WAR {p['war']})" if p.get("war") else ""
            lines.append(f"  {p['order']}번 {p['position']} {p['name']}{war_str}")

    return "\n".join(lines)


if __name__ == "__main__":
    import sys
    sys.stdout.reconfigure(encoding="utf-8")

    # 어제 경기 테스트
    result = get_pregame_lineup("20260401HTLG0")
    if result:
        print(f"Available: {result['available']}")
        print(f"Home ({result['home_team']}):")
        for p in result["home_lineup"][:9]:
            print(f"  {p['order']}. {p['position']:4s} {p['name']:6s} WAR={p['war']}")
        print(f"Away ({result['away_team']}):")
        for p in result["away_lineup"][:9]:
            print(f"  {p['order']}. {p['position']:4s} {p['name']:6s} WAR={p['war']}")
    else:
        print("Failed")
