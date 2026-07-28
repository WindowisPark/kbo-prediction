"""
경기별 투수 등판 기록 수집 → data/pitching_logs.jsonl

as-of 선발 스탯(경기 전날까지 누적)과 불펜 소진 피처의 원천 데이터.
기존 pitching CSV는 시즌 최종 합계라 as-of 복원이 불가능했다.

사용법:
  python scripts/collect_pitching_logs.py            # 미수집 경기 전체
  python scripts/collect_pitching_logs.py --limit 20 # 앞 20경기만 (테스트)
"""
import sys
import json
import time
import logging
import argparse
from pathlib import Path

import requests

ROOT = Path(__file__).parent.parent
sys.path.insert(0, str(ROOT))

logging.basicConfig(level=logging.INFO, format="%(asctime)s [%(levelname)s] %(message)s")
logger = logging.getLogger(__name__)

from backend.scrapers.kbo_pitching_log import (
    fetch_pitching_log, HEADERS, _load_name_cache, _save_name_cache,
)

RESULTS_FILE = ROOT / "data" / "daily_results.jsonl"
LOG_FILE = ROOT / "data" / "pitching_logs.jsonl"


def _read_jsonl(path: Path) -> list[dict]:
    if not path.exists():
        return []
    return [json.loads(line) for line in path.read_text(encoding="utf-8").splitlines() if line.strip()]


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--limit", type=int, default=None, help="처리할 경기 수 상한")
    parser.add_argument("--delay", type=float, default=0.3, help="요청 간 대기 (초)")
    args = parser.parse_args()

    games = _read_jsonl(RESULTS_FILE)
    done_ids = {r["game_id"] for r in _read_jsonl(LOG_FILE)}
    todo = [g for g in games if g["game_id"] not in done_ids]
    if args.limit:
        todo = todo[: args.limit]

    logger.info(f"전체 {len(games)}경기 | 수집됨 {len(done_ids)} | 대상 {len(todo)}")
    if not todo:
        logger.info("수집할 경기 없음")
        return

    session = requests.Session()
    session.headers.update(HEADERS)
    cache = _load_name_cache()
    cache_size_before = len(cache)

    ok = failed = records_total = 0
    with open(LOG_FILE, "a", encoding="utf-8") as f:
        for i, game in enumerate(todo, 1):
            gid = game["game_id"]
            records = fetch_pitching_log(gid, session=session, cache=cache)
            if not records:
                failed += 1
                logger.warning(f"  [{i}/{len(todo)}] {gid} 수집 실패")
                continue
            for rec in records:
                rec["date"] = game["date"]
                rec["team"] = game["home_team"] if rec["side"] == "home" else game["away_team"]
                f.write(json.dumps(rec, ensure_ascii=False) + "\n")
            ok += 1
            records_total += len(records)
            if i % 25 == 0 or i == len(todo):
                f.flush()
                logger.info(f"  [{i}/{len(todo)}] {gid} — 누적 {records_total}건, 실패 {failed}")
            time.sleep(args.delay)

    _save_name_cache(cache)
    session.close()
    logger.info(f"완료: {ok}경기 / {records_total}등판 기록 (실패 {failed})")
    logger.info(f"선수명 캐시: {cache_size_before} -> {len(cache)}")


if __name__ == "__main__":
    main()
