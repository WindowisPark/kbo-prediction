# 피처 엔지니어링 명세

**파일**: `backend/features/build_features.py`
**매트릭스**: `data/features/game_features_v5.csv` (15,485행 × **89열**, 2026-07-28 기준)

모델이 실제로 쓰는 피처는 `xgboost_model.py:FEATURES` **59개**다. 89열과 59개의
차이는 메타 컬럼(date/team/score 등)과 미사용 열이다. `_prepare()`가 없는 열을
조용히 드롭하므로, FEATURES에 이름을 추가해도 CSV에 없으면 **무증상으로 무시된다**.

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

### 선발투수 실제 스탯 — v3~v4 (14개) ⚠️ 누수, 프로덕션 미사용

**이 피처들은 현재 `game_features_v5.csv`(89열)에도 `xgboost_model.py:FEATURES`에도 없다.**
`build_features.py`에 생성 코드 자체가 없어 v5 재빌드로는 만들어지지 않는다.

그리고 복원해서도 안 된다 — `*_actual`은 **시즌 최종 확정 스탯**이라 미래정보 누수다.
2024시즌 8선발 이상 투수 40명 전원의 값이 시즌 내내 상수였다. 상세는
[models.md](models.md#v4-629는-누수였다). 대체 경로는 `kbo_pitching_log.py` 기반 as-of 누적.

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
- [ ] ~~선발투수: 시즌 누적 (해당 경기 전까지)~~ — **거짓이었음.**
      v4 `sp_*_actual`은 시즌 최종 스탯이었다 (2026-07-28 실측). v5에는 해당 피처
      자체가 없어 현재 프로덕션은 누수 없음. as-of 재구현은 v2 과제.

**검증 방법**: 동일 (선수, 시즌) 조합에서 스탯 값이 경기마다 변하는지 확인한다.
값이 상수면 시즌 최종 스탯 = 누수. 체크박스만 믿지 말 것 — 위 항목이 그렇게 통과됐다.
