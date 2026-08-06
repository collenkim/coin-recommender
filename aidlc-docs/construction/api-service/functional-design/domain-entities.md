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
| expected_return | REAL | 기대수익률 |
| n | INTEGER | 표본 수 |
| hit_count | INTEGER | 적중 횟수 |

PRIMARY KEY (run_time, market)

## HealthStatus
`GET /health` 응답

| Field | Type | 설명 |
|---|---|---|
| status | "ok" \| "error" | 전체 상태 |
| db_connected | bool | DB 연결 확인 결과 |
