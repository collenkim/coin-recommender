# Domain Entities — Unit 3: api-service

## PipelineRunResult
`Pipeline.run_recommendation_pipeline()`의 반환값

| Field | Type | 설명 |
|---|---|---|
| run_time | datetime (UTC) | 실행 시각 |
| regime_bullish | bool | 이번 회차 레짐 판정 결과 |
| recommendations | list[Recommendation] | 추천 리스트 (0개 가능) |

## 영속화 스키마 (DataStore 확장)

### `pipeline_runs` 테이블
| Column | Type | 설명 |
|---|---|---|
| run_time | TEXT (ISO, PK) | 실행 시각 |
| regime_bullish | INTEGER (0/1) | 레짐 판정 결과 |

### `recommendations` 테이블
| Column | Type | 설명 |
|---|---|---|
| run_time | TEXT | 해당 실행 시각 (pipeline_runs 참조, 논리적 FK) |
| market | TEXT | 마켓 코드 |
| source | TEXT (nullable, 신규 BR11) — 추천 거래소 ("upbit" \| "binance") |
| expected_return | REAL | 기대수익률 |
| n | INTEGER | 표본 수 |
| hit_count | INTEGER | 적중 횟수 |
| target_reached | INTEGER (nullable, 0/1) | 신규 (BR9/BR11) — 사후 판별 결과, 미판별이면 NULL |
| realized_return | REAL (nullable) | 신규 (BR9/BR11) — 사후 판별된 실제 수익률, 미판별이면 NULL |
| evaluated_at | TEXT (nullable, ISO) | 신규 (BR9) — 판별 수행 시각, 미판별이면 NULL |
| entry_time | TEXT (nullable, ISO) | 신규 (BR12) — 진입 기준 봉의 마감 시각 |
| entry_price | REAL (nullable) | 신규 (BR12) — 진입 기준 봉의 종가 |
| max_drawdown | REAL (nullable) | 신규 (BR12) — 과거 표본의 최악 진입 후 낙폭 (음수) |

`target_price`(진입가×1.04)와 `exit_deadline`(진입+24시간)은 파생값이라 저장하지 않고 API 응답 시 계산한다 (BR12).

PRIMARY KEY (run_time, market)

**마이그레이션 (NFR-L3, NFR-B2)**: 이미 배포된 DB에도 안전하게 적용되도록, `_init_schema()`에서 `ALTER TABLE recommendations ADD COLUMN ...`을 실행하고 "duplicate column" 에러(이미 컬럼이 있는 경우)는 무시한다. `CREATE TABLE IF NOT EXISTS`만으로는 이미 존재하는 테이블에 새 컬럼이 추가되지 않으므로 별도 처리 필요. `source` 컬럼은 기존 행에는 NULL로 남지만(과거엔 전부 업비트였음), API 조회 시 NULL을 "upbit"으로 취급해 하위 호환을 유지한다 (과거 데이터는 실제로 전부 업비트 추천이었으므로 이 해석이 사실과 일치, NFR-B2).

## RecommendationOutcome (조회용, Unit 2 도메인 재사용)
Unit 2의 `RecommendationOutcome`(analytics-backtest 도메인)을 그대로 사용 — Unit 3는 이를 위 `recommendations` 테이블의 3개 신규 컬럼에 매핑해 저장/조회한다. 별도 테이블을 만들지 않음 (1추천:1결과의 단순한 관계라 컬럼 추가가 조인보다 단순, NFR-L1 취지).

## HealthStatus
`GET /health` 응답

| Field | Type | 설명 |
|---|---|---|
| status | "ok" \| "error" | 전체 상태 |
| db_connected | bool | DB 연결 확인 결과 |
