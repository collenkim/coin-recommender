# Unit of Work Dependencies — coin-recommender

| Unit | Depends On | Reason |
|---|---|---|
| Unit 1 (data-pipeline) | — | 외부 API/DB만 의존, 다른 유닛에 의존하지 않음 |
| Unit 2 (analytics-backtest) | Unit 1 | `Backtest`/`Scorer`가 `DataStore`로 저장된 캔들을 조회 |
| Unit 3 (api-service) | Unit 1, Unit 2 | `Pipeline`이 Unit 1의 수집 컴포넌트와 Unit 2의 `Scorer`를 오케스트레이션 |

**빌드 순서**: Unit 1 → Unit 2 → Unit 3 (순차, 병렬화 불가 — Unit 3는 Unit 1·2 전체를 조합)

**검증**: `component-dependency.md`의 Unit Boundary Consistency Check와 일치, 순환 의존 없음, 역방향 의존 없음 (Application Design 중 발견했던 binance_client→features 역전 문제는 레짐 로직을 Scorer로 이동해 해소됨)
