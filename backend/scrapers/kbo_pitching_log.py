"""
경기별 투수 등판 기록을 BoxScore에서 추출.

기존 `data/processed/pitching_2000_2025.csv`는 (선수, 시즌) 단위 최종 합계라
경기 시점까지의 as-of 스탯을 복원할 수 없다. 그래서 v4의 `sp_*_actual`이
시즌 최종 ERA를 쓰는 누수 피처가 됐다. 이 모듈은 그 대체 원천이다.

BoxScore Table 3/4 (원정/홈 투수진) 열 구성:
  선수명 | 등판 | 결과 | 승 | 패 | 세 | 이닝 | 타자 | 투구수 | 타수
        | 피안타 | 홈런 | 4사구 | 삼진 | 실점 | 자책 | 평균자책점

주의 — 원정팀은 선수명이 이름으로, 홈팀은 KBO 선수 ID(예: "68220")로 온다.
ID는 선수 상세 페이지로 이름을 해소하고 `data/cache/player_names.json`에 캐시한다.

이닝 표기: "5", "1/3", "2/3", "5 1/3" 형태 → 아웃카운트(정수)로 정규화.
등판 표기: "선발" 또는 구원 등판 시점("6.2" = 6회 2아웃 후 등판).
"""
import json
import time
import logging
from pathlib import Path

import requests
from bs4 import BeautifulSoup

logger = logging.getLogger(__name__)

BASE_URL = "https://www.koreabaseball.com"
HEADERS = {
    "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36",
    "Referer": f"{BASE_URL}/Schedule/GameCenter/Main.aspx",
}
PLAYER_URL = f"{BASE_URL}/Record/Player/PitcherDetail/Basic.aspx"
_NAME_SELECTOR = "#cphContents_cphContents_cphContents_playerProfile_lblName"

CACHE_FILE = Path(__file__).parent.parent.parent / "data" / "cache" / "player_names.json"

# BoxScore 투수 테이블 열 순서 → 저장 키
_COLUMNS = [
    "name", "appearance", "decision", "w", "l", "sv",
    "innings", "tbf", "pitches", "ab", "h", "hr", "bb_hbp", "so", "r", "er", "era",
]
_INT_FIELDS = ("w", "l", "sv", "tbf", "pitches", "ab", "h", "hr", "bb_hbp", "so", "r", "er")


def _load_name_cache() -> dict[str, str]:
    if CACHE_FILE.exists():
        try:
            return json.loads(CACHE_FILE.read_text(encoding="utf-8"))
        except json.JSONDecodeError:
            logger.warning("player_names.json 파싱 실패 — 캐시 무시")
    return {}


def _save_name_cache(cache: dict[str, str]) -> None:
    CACHE_FILE.parent.mkdir(parents=True, exist_ok=True)
    CACHE_FILE.write_text(json.dumps(cache, ensure_ascii=False, indent=2), encoding="utf-8")


def resolve_player_name(player_id: str, session: requests.Session, cache: dict[str, str],
                        retries: int = 3) -> str:
    """KBO 선수 ID → 이름. 캐시 우선, 실패 시 ID를 그대로 돌려준다.

    해소에 실패하면 그 선수의 등판이 이름 기준 누적에서 분리되므로 재시도한다.
    (record에 player_id를 함께 남기므로 사후 재해소도 가능)
    """
    if player_id in cache:
        return cache[player_id]
    for attempt in range(retries):
        try:
            resp = session.get(PLAYER_URL, params={"playerId": player_id}, timeout=20)
            if resp.status_code == 200:
                tag = BeautifulSoup(resp.text, "html.parser").select_one(_NAME_SELECTOR)
                if tag:
                    name = tag.get_text(strip=True)
                    if name:
                        cache[player_id] = name
                        return name
            logger.warning(f"  선수 ID {player_id} 조회 HTTP {resp.status_code} "
                           f"(attempt {attempt + 1}/{retries})")
        except requests.RequestException as e:
            logger.warning(f"  선수 ID {player_id} 이름 조회 실패 "
                           f"(attempt {attempt + 1}/{retries}): {e}")
        if attempt < retries - 1:
            time.sleep(2 ** attempt)
    return player_id


def parse_innings_to_outs(text: str) -> int:
    """이닝 표기를 아웃카운트로. "5"→15, "1/3"→1, "5 1/3"→16, ""→0."""
    text = text.strip()
    if not text:
        return 0
    outs = 0
    for token in text.split():
        if "/" in token:
            num, _, den = token.partition("/")
            try:
                if int(den) == 3:
                    outs += int(num)
            except ValueError:
                pass
        else:
            try:
                outs += int(token) * 3
            except ValueError:
                pass
    return outs


def _cell_text(cell: dict) -> str:
    return BeautifulSoup(cell.get("Text", ""), "html.parser").get_text(strip=True)


def _to_int(text: str) -> int:
    try:
        return int(text)
    except (TypeError, ValueError):
        return 0


def fetch_pitching_log(game_id: str, session: requests.Session | None = None,
                       cache: dict[str, str] | None = None) -> list[dict] | None:
    """한 경기의 양팀 투수 등판 기록. 실패 시 None."""
    own_session = session is None
    if own_session:
        session = requests.Session()
        session.headers.update(HEADERS)
    own_cache = cache is None
    if own_cache:
        cache = _load_name_cache()

    try:
        resp = session.post(
            f"{BASE_URL}/ws/Schedule.asmx/GetBoxScore",
            data={"gameId": game_id, "leId": "1", "srId": "0", "seasonId": game_id[:4]},
            timeout=15,
        )
        if resp.status_code != 200:
            logger.warning(f"  {game_id}: BoxScore HTTP {resp.status_code}")
            return None
        tables = resp.json().get("tables", [])
    except (requests.RequestException, ValueError) as e:
        logger.warning(f"  {game_id}: BoxScore 요청 실패 — {e}")
        return None

    if len(tables) < 5:
        logger.warning(f"  {game_id}: 테이블 {len(tables)}개 — 투수진 없음")
        return None

    records: list[dict] = []
    for table, side in ((tables[3], "away"), (tables[4], "home")):
        for row in table.get("rows", []):
            cells = row.get("row", [])
            if len(cells) < len(_COLUMNS):
                continue
            values = [_cell_text(c) for c in cells[: len(_COLUMNS)]]
            rec = dict(zip(_COLUMNS, values))

            # 홈팀은 선수명이 KBO 선수 ID로 온다
            raw_name = rec["name"]
            if raw_name.isdigit():
                rec["player_id"] = raw_name
                rec["name"] = resolve_player_name(raw_name, session, cache)
            else:
                rec["player_id"] = ""

            rec["game_id"] = game_id
            rec["side"] = side
            rec["is_starter"] = rec["appearance"] == "선발"
            rec["outs"] = parse_innings_to_outs(rec["innings"])
            for field in _INT_FIELDS:
                rec[field] = _to_int(rec[field])
            records.append(rec)

    if own_cache:
        _save_name_cache(cache)
    if own_session:
        session.close()

    return records or None
