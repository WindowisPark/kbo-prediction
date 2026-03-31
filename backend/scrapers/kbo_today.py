"""
오늘/다음 경기일의 KBO 경기 일정을 가져오는 모듈.

KBO 공식 사이트 API:
  - GetKboGameDate: 이전/현재/다음 경기일 조회
  - GetKboGameList: 경기 상세 (선발투수, 구장, 순위 포함)
  - GetScheduleList: 월별 경기 목록
"""
import requests
import re
from datetime import datetime
from bs4 import BeautifulSoup

BASE_URL = "https://www.koreabaseball.com"
HEADERS = {
    "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36",
    "Referer": f"{BASE_URL}/Schedule/Schedule.aspx",
}


def get_next_game_date() -> dict:
    """KBO의 이전/현재/다음 경기일을 조회."""
    session = requests.Session()
    session.headers.update(HEADERS)

    today = datetime.now().strftime("%Y%m%d")
    resp = session.post(
        f"{BASE_URL}/ws/Main.asmx/GetKboGameDate",
        data={"leId": "1", "srId": "0,1,3,4,5,7,8,9", "date": today},
        timeout=15,
    )
    data = resp.json()
    return {
        "prev": data.get("BEFORE_G_DT", ""),
        "current": data.get("NOW_G_DT", ""),
        "current_text": data.get("NOW_G_DT_TEXT", ""),
        "next": data.get("AFTER_G_DT", ""),
    }


def get_games_for_date(target_date: str) -> list[dict]:
    """
    특정 날짜의 경기 목록을 가져온다.

    Args:
        target_date: YYYYMMDD 형식
    Returns:
        [{"away_team", "home_team", "time", "status", "game_id"}, ...]
    """
    session = requests.Session()
    session.headers.update(HEADERS)

    year = target_date[:4]
    month = target_date[4:6]
    day = target_date[6:8]
    match_str = f"{month}.{day}"

    resp = session.post(
        f"{BASE_URL}/ws/Schedule.asmx/GetScheduleList",
        data={
            "leId": "1", "srIdList": "0,9,6",
            "seasonId": year, "gameMonth": month, "teamId": "",
        },
        timeout=15,
    )
    data = resp.json()
    rows = data.get("rows", [])

    current_date = ""
    games = []

    for row_obj in rows:
        cells = row_obj.get("row", [])

        for cell in cells:
            cls = cell.get("Class") or ""
            if cls == "day":
                dm = re.search(r"(\d{2}\.\d{2})", cell.get("Text", ""))
                if dm:
                    current_date = dm.group(1)

        if current_date != match_str:
            continue

        play_text = ""
        time_text = ""
        review_text = ""

        for cell in cells:
            cls = cell.get("Class") or ""
            text = cell.get("Text") or ""
            if cls == "play":
                play_text = text
            elif cls == "time":
                time_text = text
            elif "etc" in cls.lower() or cls == "relay":
                review_text = text

        if not play_text:
            continue

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

        game_id = ""
        id_match = re.search(r"gameId=(\w+)", review_text)
        if id_match:
            game_id = id_match.group(1)

        time_soup = BeautifulSoup(time_text, "html.parser")
        time_str = time_soup.get_text(strip=True)

        if len(teams) >= 2:
            status = "scheduled"
            if len(scores) >= 2:
                status = "final"

            games.append({
                "away_team": teams[0],
                "home_team": teams[-1],
                "time": time_str,
                "away_score": int(scores[0]) if len(scores) >= 2 else None,
                "home_score": int(scores[1]) if len(scores) >= 2 else None,
                "status": status,
                "game_id": game_id,
                "date": f"{year}-{month}-{day}",
            })

    return games


def get_game_list(target_date: str) -> list[dict]:
    """
    GetKboGameList로 상세 경기 정보 가져오기.
    선발투수, 구장, 순위, 라인업 공개 여부 포함.
    """
    session = requests.Session()
    session.headers.update(HEADERS)

    resp = session.post(
        f"{BASE_URL}/ws/Main.asmx/GetKboGameList",
        data={"leId": "1", "srId": "0,9", "date": target_date},
        timeout=15,
    )

    if resp.status_code != 200:
        return []

    raw = resp.json()
    if isinstance(raw, dict):
        raw = raw.get("game", raw.get("d", raw.get("rows", [])))
    if isinstance(raw, str):
        import json
        raw = json.loads(raw)

    games = []
    for g in raw:
        state = str(g.get("GAME_STATE_SC", "0"))
        if state == "0":
            status = "scheduled"
        elif state == "1":
            status = "in_progress"
        elif state == "3":
            status = "final"
        else:
            status = "scheduled"

        cancel = str(g.get("CANCEL_SC_ID", "0"))
        if cancel != "0":
            status = "cancelled"

        away_score = g.get("T_SCORE_CN")
        home_score = g.get("B_SCORE_CN")
        try:
            away_score = int(away_score) if away_score else None
            home_score = int(home_score) if home_score else None
        except (ValueError, TypeError):
            away_score = None
            home_score = None

        dt = g.get("G_DT", target_date)
        games.append({
            "game_id": g.get("G_ID", ""),
            "date": f"{dt[:4]}-{dt[4:6]}-{dt[6:8]}",
            "time": g.get("G_TM", ""),
            "away_team": g.get("AWAY_NM", ""),
            "home_team": g.get("HOME_NM", ""),
            "away_score": away_score,
            "home_score": home_score,
            "status": status,
            "stadium": g.get("S_NM", ""),
            "away_starter": (g.get("T_PIT_P_NM") or "").strip(),
            "home_starter": (g.get("B_PIT_P_NM") or "").strip(),
            "away_rank": g.get("T_RANK_NO"),
            "home_rank": g.get("B_RANK_NO"),
            "lineup_available": g.get("LINEUP_CK", 0) == 1,
            "tv": g.get("TV_IF", ""),
        })

    return games


def get_today_games() -> list[dict]:
    """오늘(또는 가장 가까운 경기일)의 경기 목록 — 선발투수 포함."""
    dates = get_next_game_date()
    target = dates["current"]
    if not target:
        return []
    return get_game_list(target)


if __name__ == "__main__":
    import sys
    sys.stdout.reconfigure(encoding="utf-8")

    dates = get_next_game_date()
    print(f"경기일: {dates['current_text']}")

    games = get_today_games()
    print(f"\n{len(games)}경기:")
    for g in games:
        score = f"{g['away_score']}-{g['home_score']}" if g["status"] == "final" else g["status"]
        sp = f"{g['away_starter']} vs {g['home_starter']}" if g["away_starter"] else "TBD"
        print(f"  {g['time']:6s} | {g['away_team']:4s} @ {g['home_team']:4s} | {g['stadium']:4s} | {score:12s} | SP: {sp}")
