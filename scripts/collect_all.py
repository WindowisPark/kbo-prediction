"""
전체 데이터 수집 오케스트레이션 스크립트.

순서:
1. Kaggle 데이터셋 다운로드 (빠름)
2. KBO 공식 사이트에서 경기 결과 스크래핑 (느림)
3. KBO 공식 사이트에서 선수/팀 스탯 스크래핑 (느림)
4. 데이터 검증 및 요약

사용법:
  python scripts/collect_all.py                    # 전체 수집
  python scripts/collect_all.py --skip-kaggle      # Kaggle 건너뛰기
  python scripts/collect_all.py --year 2024        # 특정 시즌만
"""
import argparse
import sys
from pathlib import Path

# 프로젝트 루트를 path에 추가
PROJECT_ROOT = Path(__file__).parent.parent
sys.path.insert(0, str(PROJECT_ROOT))

from backend.scrapers.kbo_game_scraper import KBOGameScraper
from backend.scrapers.kbo_stats_scraper import KBOStatsScraper


def collect_kaggle():
    """Kaggle 데이터셋 다운로드."""
    print("\n" + "=" * 60)
    print("STEP 1: Kaggle 데이터셋 다운로드")
    print("=" * 60)
    from scripts.download_kaggle import main as download_main
    download_main()


def collect_games(start_year: int, end_year: int):
    """KBO 경기 결과 스크래핑."""
    print("\n" + "=" * 60)
    print(f"STEP 2: KBO 경기 결과 수집 ({start_year}~{end_year})")
    print("=" * 60)
    scraper = KBOGameScraper(output_dir=PROJECT_ROOT / "data" / "raw")
    df = scraper.scrape_range(start_year, end_year)
    print(f"경기 수집 완료: {len(df)}경기")
    return df


def collect_stats(start_year: int, end_year: int):
    """KBO 선수/팀 스탯 스크래핑."""
    print("\n" + "=" * 60)
    print(f"STEP 3: KBO 선수/팀 스탯 수집 ({start_year}~{end_year})")
    print("=" * 60)
    scraper = KBOStatsScraper(output_dir=PROJECT_ROOT / "data" / "raw")
    scraper.scrape_range(start_year, end_year)
    print("스탯 수집 완료")


def summarize():
    """수집된 데이터 요약."""
    print("\n" + "=" * 60)
    print("STEP 4: 데이터 요약")
    print("=" * 60)
    raw_dir = PROJECT_ROOT / "data" / "raw"
    csv_files = sorted(raw_dir.glob("*.csv"))
    total_size = 0
    for f in csv_files:
        size_mb = f.stat().st_size / (1024 * 1024)
        total_size += size_mb
        print(f"  {f.name:50s} {size_mb:6.1f} MB")
    print(f"\n  총 {len(csv_files)}개 파일, {total_size:.1f} MB")


def main():
    parser = argparse.ArgumentParser(description="KBO 데이터 수집")
    parser.add_argument("--skip-kaggle", action="store_true", help="Kaggle 다운로드 건너뛰기")
    parser.add_argument("--skip-scrape", action="store_true", help="스크래핑 건너뛰기")
    parser.add_argument("--year", type=int, help="특정 시즌만 수집")
    parser.add_argument("--start-year", type=int, default=2000)
    parser.add_argument("--end-year", type=int, default=2025)
    args = parser.parse_args()

    start = args.year or args.start_year
    end = args.year or args.end_year

    if not args.skip_kaggle:
        collect_kaggle()

    if not args.skip_scrape:
        collect_games(start, end)
        collect_stats(start, end)

    summarize()


if __name__ == "__main__":
    main()
