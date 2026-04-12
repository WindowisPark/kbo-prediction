"""
경기 전 라인업 수집 — KBO GetLineUpAnalysis API + 예상 라인업 추론.

확정 라인업: 경기 ~1.5시간 전 공개 시 GetLineUpAnalysis API.
예상 라인업: 최근 경기 라인업에서 포지션별 최빈 선수 추출.

사용법:
  lineup = get_pregame_lineup("20260401HTLG0")
  expected = get_expected_lineup("LG", num_games=5)
"""
import json
import logging
from collections import Counter
from datetime import datetime, timedelta

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


def _collect_recent_lineups(
    team_name: str,
    num_games: int = 10,
    home_only: bool | None = None,
) -> list[tuple[list[dict], float]]:
    """
    최근 경기 라인업을 수집 (가중치 포함).

    Args:
        team_name: 팀명
        num_games: 수집할 경기 수
        home_only: True=홈만, False=원정만, None=전체

    Returns:
        [(lineup, weight), ...] — weight는 최근 경기일수록 높음
    """
    from backend.scrapers.kbo_today import get_game_list

    collected: list[tuple[list[dict], float]] = []
    check_date = datetime.now()

    for _ in range(45):  # 최대 45일 전까지
        check_date -= timedelta(days=1)
        date_str = check_date.strftime("%Y%m%d")

        try:
            games = get_game_list(date_str)
        except Exception:
            continue

        for game in games:
            if game["status"] != "final":
                continue
            if team_name not in (game.get("home_team", ""), game.get("away_team", "")):
                continue

            is_home = game.get("home_team", "") == team_name
            if home_only is True and not is_home:
                continue
            if home_only is False and is_home:
                continue

            game_id = game.get("game_id", "")
            if not game_id:
                continue

            lineup_data = get_pregame_lineup(game_id)
            if not lineup_data or not lineup_data.get("available"):
                continue

            players = lineup_data["home_lineup"] if is_home else lineup_data["away_lineup"]
            if players:
                # 최근 경기 가중치: 0.9^(n) — 가장 최근=1.0, 그 전=0.9, ...
                weight = 0.9 ** len(collected)
                collected.append((players[:9], weight))

            if len(collected) >= num_games:
                break

        if len(collected) >= num_games:
            break

    return collected


def _pick_lineup_no_duplicates(
    order_scores: dict[str, dict[str, float]],
) -> list[dict]:
    """
    타순별 가중 점수에서 중복 없이 최적 라인업 선택.

    Greedy: 점수 높은 순으로 배정, 이미 선택된 선수는 스킵.
    """
    # (order, name|pos, score) 전체를 모아서 점수 내림차순 정렬
    candidates = []
    for order, players in order_scores.items():
        for name_pos, score in players.items():
            candidates.append((order, name_pos, score))
    candidates.sort(key=lambda x: x[2], reverse=True)

    used_names: set[str] = set()
    assigned: dict[str, tuple[str, float]] = {}  # order → (name_pos, score)

    for order, name_pos, score in candidates:
        name = name_pos.split("|", 1)[0]
        if order in assigned or name in used_names:
            continue
        assigned[order] = (name_pos, score)
        used_names.add(name)

    result = []
    for order in sorted(assigned.keys(), key=lambda x: int(x) if x.isdigit() else 99):
        name_pos, score = assigned[order]
        name, position = name_pos.split("|", 1)
        result.append({
            "order": order,
            "position": position,
            "name": name,
            "score": round(score, 2),
        })

    return result[:9]


def get_expected_lineup(
    team_name: str,
    num_games: int = 10,
    is_home: bool | None = None,
) -> dict:
    """
    최근 경기 라인업에서 예상 선발 타선 추론 (개선 v2).

    개선점:
      - 10경기 lookback (기존 5)
      - 최근 경기 가중치 (exponential decay 0.9^n)
      - 홈/원정 분리 → 해당 상황 라인업 우선
      - 타순 간 중복 제거 (greedy 최적 배정)

    Returns:
        {
            "estimated": True,
            "games_used": int,
            "lineup": [{"order", "position", "name", "score"}, ...],
        }
    """
    # 1) 홈/원정 특화 라인업 시도
    collected = []
    if is_home is not None:
        collected = _collect_recent_lineups(team_name, num_games, home_only=is_home)

    # 부족하면 전체에서 보충
    if len(collected) < 5:
        collected = _collect_recent_lineups(team_name, num_games, home_only=None)

    if not collected:
        return {"estimated": True, "games_used": 0, "lineup": []}

    # 2) 타순별 가중 점수 집계
    order_scores: dict[str, dict[str, float]] = {}
    for lineup, weight in collected:
        for p in lineup:
            order = p["order"]
            key = f"{p['name']}|{p['position']}"
            if order not in order_scores:
                order_scores[order] = {}
            order_scores[order][key] = order_scores[order].get(key, 0) + weight

    # 3) 중복 없이 최적 배정
    estimated = _pick_lineup_no_duplicates(order_scores)

    return {
        "estimated": True,
        "games_used": len(collected),
        "lineup": estimated,
    }


def format_expected_lineup_context(team_name: str, expected: dict) -> str:
    """예상 라인업을 LLM 맥락 문자열로 변환."""
    if not expected or not expected.get("lineup"):
        return ""

    n = expected.get("games_used", 0)
    lines = [f"\n### {team_name} 예상 타선 (최근 {n}경기 기반)"]
    for p in expected["lineup"]:
        score = p.get("score", 0)
        freq = p.get("frequency")  # backward compat
        if freq is not None:
            detail = f" [{freq}/{n}경기]"
        else:
            detail = f" [신뢰도 {score:.1f}]" if n > 0 else ""
        lines.append(f"  {p['order']}번 {p['position']} {p['name']}{detail}")

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
