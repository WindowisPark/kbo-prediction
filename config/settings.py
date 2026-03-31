"""프로젝트 전역 설정"""
from pathlib import Path

# 경로
PROJECT_ROOT = Path(__file__).parent.parent
DATA_DIR = PROJECT_ROOT / "data"
RAW_DIR = DATA_DIR / "raw"
PROCESSED_DIR = DATA_DIR / "processed"
FEATURES_DIR = DATA_DIR / "features"

# KBO 설정
KBO_TEAMS = {
    "두산": "Doosan Bears",
    "LG": "LG Twins",
    "KIA": "KIA Tigers",
    "삼성": "Samsung Lions",
    "롯데": "Lotte Giants",
    "한화": "Hanwha Eagles",
    "SK": "SK Wyverns",        # 2021~ SSG
    "SSG": "SSG Landers",
    "NC": "NC Dinos",          # 2013~
    "kt": "kt wiz",            # 2015~
    "키움": "Kiwoom Heroes",   # 넥센→키움
    "넥센": "Nexen Heroes",
    "히어로즈": "Heroes",
    "현대": "Hyundai Unicorns", # ~2007
    "우리": "Woori Heroes",
}

# 팀명 변경 이력 (통합용)
TEAM_NAME_MAP = {
    # 히어로즈 계보
    "현대": "Heroes", "우리": "Heroes", "넥센": "Heroes",
    "히어로즈": "Heroes", "키움": "Heroes",
    # SK → SSG
    "SK": "SK/SSG", "SSG": "SK/SSG",
}

SEASONS = list(range(2000, 2026))
MIN_SEASON = 2000
MAX_SEASON = 2025

# 모델 설정
ROLLING_WINDOWS = [10, 20, 30]  # 최근 N경기 rolling stats
TRAIN_TEST_SPLIT_YEAR = 2023    # 2000-2022 학습, 2023-2024 검증, 2025 테스트

# LLM 에이전트 설정
AGENT_MODEL = "claude-sonnet-4-6-20250514"
DEBATE_ROUNDS = 2
NUM_AGENTS = 3
