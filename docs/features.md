# 피처 엔지니어링 명세

**파일**: `backend/features/build_features.py`
**매트릭스**: `data/features/game_features_v5.csv` (15,026행 × 103열)

## 카테고리별 피처

### Rolling Stats (24개)
| 피처 | 설명 | Window |
|------|------|--------|
| `home/away_win_pct_{10,20,30}` | 최근 N경기 승률 | 10/20/30 |
| `home/away_run_diff_{10,20,30}` | 최근 N경기 득실차 평균 | 10/20/30 |
| `home/away_runs_for_{10,20,30}` | 최근 N경기 평균 득점 | 10/20/30 |
| `home/away_runs_against_{10,20,30}` | 최근 N경기 평균 실점 | 10/20/30 |

### 홈/원정 분리 (2개)
| 피처 | 설명 |
|------|------|
| `home_home_win_pct` | 홈 경기만의 최근 10경기 승률 |
| `away_away_win_pct` | 원정 경기만의 최근 10경기 승률 |

### 연승/연패 (2개)
| 피처 | 설명 |
|------|------|
| `home_streak` | 양수=연승, 음수=연패 |
| `away_streak` | 동일 |

### 상대전적 (2개)
| 피처 | 설명 |
|------|------|
| `h2h_win_pct` | 최근 10회 맞대결 홈팀 승률 |
| `h2h_count` | 올시즌 맞대결 횟수 |

### ELO (4개)
| 피처 | 설명 |
|------|------|
| `home_elo` / `away_elo` | ELO 레이팅 |
| `elo_diff` | home - away |
| `elo_expected` | ELO 기반 홈팀 기대 승률 |

### 팀 시즌 스탯 — 전년도 기반 (26개)
| 피처 | 설명 |
|------|------|
| `home/away_ops, obp, slg, hr, war` | 타격 |
| `home/away_era, fip, whip, war_pit` | 투수 |
| `home/away_sp_era, sp_fip, sp_whip, sp_war` | 선발투수 (팀 평균) |
| `home/away_wrc_plus` | 공격 종합 |

**누수 방지**: 전년도 70% + 2년전 30% 가중 블렌딩

### 차이 피처 (11개)
| 피처 | 계산 |
|------|------|
| `win_pct_diff_{10,20,30}` | home - away 승률 차 |
| `run_diff_diff_{10,20,30}` | home - away 득실차 차 |
| `ops_diff` | 공격력 차이 |
| `era_diff` | 투수력 차이 (away-home, 역전) |
| `sp_era_diff` / `sp_war_diff` | 선발투수 차이 |
| `bat_war_diff` / `streak_diff` | 타자 WAR / 연승 차이 |
| `home_away_split_diff` | 홈-원정 성향 차이 |

### 시간 (4개)
| 피처 | 설명 |
|------|------|
| `month` | 월 (3~11) |
| `day_of_week` | 요일 (0=월~6=일) |
| `is_weekend` | 주말 여부 |
| `days_into_season` | 시즌 경과일 |

### 선발투수 실제 스탯 — v3~v4 (14개)
| 피처 | 설명 |
|------|------|
| `away_starter` | 원정 선발투수 이름 |
| `away_sp_era_actual` / `home_sp_era_actual` | 해당 시즌 실제 ERA |
| `away_sp_fip_actual` / `home_sp_fip_actual` | 실제 FIP |
| `away_sp_war_actual` / `home_sp_war_actual` | 실제 WAR |
| `away_sp_whip_actual` / `home_sp_whip_actual` | 실제 WHIP |
| `sp_era_actual_diff` | 선발 ERA 차이 (홈-원정) |
| `sp_war_actual_diff` | 선발 WAR 차이 |
| `sp_fip_actual_diff` | 선발 FIP 차이 |
| `sp_whip_actual_diff` | 선발 WHIP 차이 |

## 누수 방지 체크리스트

- [x] 팀 스탯: 전년도 사용 (현재 시즌 X)
- [x] Rolling: `.shift(1)` — 현재 경기 미포함
- [x] ELO: 경기 전 값만 사용, 결과 후 업데이트
- [x] 상대전적: 현재 경기 미포함
- [x] 선발투수: 시즌 누적 (해당 경기 전까지)
