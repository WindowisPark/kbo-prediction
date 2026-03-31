-- KBO 예측 프로젝트 DB 스키마
-- PostgreSQL

-- 팀 정보
CREATE TABLE IF NOT EXISTS teams (
    team_id SERIAL PRIMARY KEY,
    name_kr VARCHAR(20) NOT NULL,
    name_en VARCHAR(50),
    abbreviation VARCHAR(10),
    active_from INT NOT NULL,
    active_to INT,  -- NULL이면 현재 활동중
    successor_id INT REFERENCES teams(team_id)  -- 팀명 변경 시
);

-- 선수 정보
CREATE TABLE IF NOT EXISTS players (
    player_id SERIAL PRIMARY KEY,
    name_kr VARCHAR(30) NOT NULL,
    name_en VARCHAR(50),
    position VARCHAR(10),  -- P, C, 1B, 2B, 3B, SS, LF, CF, RF, DH
    throws VARCHAR(1),     -- L, R
    bats VARCHAR(1),       -- L, R, S
    birth_date DATE
);

-- 경기 결과 (예측의 기본 단위)
CREATE TABLE IF NOT EXISTS games (
    game_id VARCHAR(20) PRIMARY KEY,
    date DATE NOT NULL,
    season INT NOT NULL,
    home_team_id INT REFERENCES teams(team_id),
    away_team_id INT REFERENCES teams(team_id),
    home_starter_id INT REFERENCES players(player_id),
    away_starter_id INT REFERENCES players(player_id),
    home_score INT,
    away_score INT,
    stadium VARCHAR(30),
    is_playoff BOOLEAN DEFAULT FALSE,
    status VARCHAR(20) DEFAULT 'final'  -- final, cancelled, suspended
);

-- 경기별 타자 기록
CREATE TABLE IF NOT EXISTS game_batting (
    id SERIAL PRIMARY KEY,
    game_id VARCHAR(20) REFERENCES games(game_id),
    player_id INT REFERENCES players(player_id),
    team_id INT REFERENCES teams(team_id),
    batting_order INT,
    ab INT, r INT, h INT,
    doubles INT, triples INT, hr INT,
    rbi INT, bb INT, so INT,
    sb INT, cs INT,
    avg DECIMAL(4,3),
    obp DECIMAL(4,3),
    slg DECIMAL(4,3)
);

-- 경기별 투수 기록
CREATE TABLE IF NOT EXISTS game_pitching (
    id SERIAL PRIMARY KEY,
    game_id VARCHAR(20) REFERENCES games(game_id),
    player_id INT REFERENCES players(player_id),
    team_id INT REFERENCES teams(team_id),
    is_starter BOOLEAN DEFAULT FALSE,
    ip DECIMAL(4,1),
    h INT, r INT, er INT,
    bb INT, so INT, hr INT,
    pitches INT,
    era DECIMAL(5,2)
);

-- 팀 rolling stats (피처 엔지니어링 결과 캐시)
CREATE TABLE IF NOT EXISTS team_features (
    id SERIAL PRIMARY KEY,
    team_id INT REFERENCES teams(team_id),
    date DATE NOT NULL,
    window_size INT NOT NULL,  -- 10, 20, 30
    win_pct DECIMAL(4,3),
    run_diff DECIMAL(5,2),
    ops DECIMAL(4,3),
    era DECIMAL(5,2),
    bullpen_era DECIMAL(5,2),
    elo_rating DECIMAL(7,2),
    streak INT,  -- 양수=연승, 음수=연패
    UNIQUE(team_id, date, window_size)
);

-- 예측 결과 저장
CREATE TABLE IF NOT EXISTS predictions (
    id SERIAL PRIMARY KEY,
    game_id VARCHAR(20) REFERENCES games(game_id),
    created_at TIMESTAMP DEFAULT NOW(),

    -- ML 모델 출력
    xgboost_home_prob DECIMAL(4,3),
    elo_home_prob DECIMAL(4,3),
    bayesian_home_prob DECIMAL(4,3),

    -- 에이전트 토론 결과
    final_home_prob DECIMAL(4,3),
    confidence DECIMAL(4,3),
    reasoning TEXT,
    debate_log JSONB,  -- 전체 토론 과정

    -- 적중 여부 (경기 종료 후 업데이트)
    actual_winner VARCHAR(10),
    is_correct BOOLEAN
);

-- 인덱스
CREATE INDEX IF NOT EXISTS idx_games_date ON games(date);
CREATE INDEX IF NOT EXISTS idx_games_season ON games(season);
CREATE INDEX IF NOT EXISTS idx_team_features_lookup ON team_features(team_id, date);
CREATE INDEX IF NOT EXISTS idx_predictions_game ON predictions(game_id);
