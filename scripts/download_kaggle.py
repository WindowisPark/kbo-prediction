"""
Kaggle에서 KBO 데이터셋을 다운로드하는 스크립트.

사전 준비:
  pip install kaggle
  ~/.kaggle/kaggle.json에 API 토큰 설정

다운로드 대상 (2000년 이후 데이터만 필터링):
  - KBO 타자 데이터 1982-2021
  - KBO 투수 데이터 1982-2021
  - KBO Player Performance 2018-2024
"""
import subprocess
import sys
import pandas as pd
from pathlib import Path

RAW_DIR = Path(__file__).parent.parent / "data" / "raw"
RAW_DIR.mkdir(parents=True, exist_ok=True)

DATASETS = [
    {
        "slug": "mattop/baseball-kbo-batting-data-1982-2021",
        "desc": "KBO 타자 데이터 1982-2021",
    },
    {
        "slug": "mattop/korean-baseball-pitching-data-1982-2021",
        "desc": "KBO 투수 데이터 1982-2021",
    },
    {
        "slug": "clementmsika/kbo-player-performance-dataset-2018-2024",
        "desc": "KBO Player Performance 2018-2024",
    },
]

MIN_YEAR = 2000


def download_dataset(slug: str, output_dir: Path):
    """kaggle CLI로 데이터셋 다운로드."""
    cmd = [
        sys.executable, "-m", "kaggle", "datasets", "download",
        "-d", slug,
        "-p", str(output_dir),
        "--unzip",
    ]
    print(f"  다운로드 중: {slug}")
    result = subprocess.run(cmd, capture_output=True, text=True)
    if result.returncode != 0:
        print(f"  ❌ 실패: {result.stderr.strip()}")
        print(f"  수동 다운로드: https://www.kaggle.com/datasets/{slug}")
        return False
    print(f"  ✅ 완료")
    return True


def filter_by_year(csv_path: Path, year_col: str = "year"):
    """2000년 이전 데이터를 제거."""
    try:
        df = pd.read_csv(csv_path, encoding="utf-8")
    except UnicodeDecodeError:
        df = pd.read_csv(csv_path, encoding="cp949")

    # year 컬럼 자동 감지
    year_candidates = [c for c in df.columns if "year" in c.lower() or "season" in c.lower()]
    if not year_candidates:
        # 첫번째 숫자형 컬럼이 연도일 수 있음
        for col in df.columns:
            if df[col].dtype in ["int64", "float64"]:
                vals = df[col].dropna()
                if len(vals) > 0 and 1982 <= vals.median() <= 2025:
                    year_candidates = [col]
                    break

    if not year_candidates:
        print(f"  ⚠️  연도 컬럼을 찾을 수 없음: {csv_path.name}")
        return

    col = year_candidates[0]
    original_len = len(df)
    df = df[df[col] >= MIN_YEAR]
    filtered_len = len(df)

    df.to_csv(csv_path, index=False, encoding="utf-8-sig")
    print(f"  필터링: {csv_path.name} ({original_len} → {filtered_len}행, 2000년 이후만)")


def main():
    print(f"📂 저장 경로: {RAW_DIR}")
    print(f"📅 필터: {MIN_YEAR}년 이후 데이터만\n")

    for ds in DATASETS:
        print(f"\n{'='*50}")
        print(f"📦 {ds['desc']}")
        success = download_dataset(ds["slug"], RAW_DIR)

        if success:
            # 다운로드된 CSV 파일들을 필터링
            for csv_file in RAW_DIR.glob("*.csv"):
                filter_by_year(csv_file)

    print(f"\n{'='*50}")
    print("완료! 다운로드된 파일:")
    for f in sorted(RAW_DIR.glob("*.csv")):
        size_mb = f.stat().st_size / (1024 * 1024)
        print(f"  {f.name} ({size_mb:.1f} MB)")


if __name__ == "__main__":
    main()
