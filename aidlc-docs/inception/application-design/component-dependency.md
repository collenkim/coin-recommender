# Component Dependencies — coin-recommender

## Dependency Matrix

| Component | Depends On | Unit |
|---|---|---|
| MarketSelector | UpbitClient | 1 |
| UpbitClient | (external: pyupbit) | 1 |
| BinanceClient | (external: requests → Binance REST) | 1 |
| DataStore | (external: sqlite3) | 1 |
| Features | — (순수 함수, 의존성 없음) | 2 |
| Backtest | DataStore, Features | 2 |
| Scorer | DataStore, Features, Backtest, BinanceClient(저장된 데이터 조회 경유) | 2 |
| Pipeline | MarketSelector, UpbitClient, BinanceClient, DataStore, Scorer, Notifier | 3 |
| Scheduler | Pipeline | 3 |
| Notifier | (external: requests → Telegram/Discord webhook) | 3 |
| API | Pipeline, Scheduler, DataStore | 3 |

## Communication Pattern

모놀리식 단일 프로세스이므로 모든 통신은 **직접 함수/메서드 호출**입니다 (네트워크 호출이나 메시지 큐 없음). 컴포넌트 간 데이터는 pydantic 모델로 타입화하여 전달합니다.

## Data Flow

```
[Upbit API] --candles--> UpbitClient --> DataStore.upsert_candles (upbit_candles table)
[Binance API] --candles--> BinanceClient --> DataStore.upsert_candles (binance_candles table)

DataStore.get_candles --> Features.compute_ichimoku --> IchimokuPoint[]
IchimokuPoint[] + market --> Scorer.check_market_regime (Binance 데이터만) --gate--> Scorer.evaluate_signal
Scorer.evaluate_signal --> SignalState --> Backtest.compute_signal_stats --> SignalStats
Scorer aggregates SignalStats across candidates, filters >= 4% --> Recommendation[]

Pipeline orchestrates: MarketSelector -> UpbitClient/BinanceClient -> DataStore -> Scorer -> DataStore(save results) -> Notifier
API (GET /recommendations) --> DataStore (read latest results)
API (POST /run) --> Pipeline.run_recommendation_pipeline()
Scheduler (hourly) --> Pipeline.run_recommendation_pipeline()
```

### Text 대체 (Mermaid 미사용 — 데이터 흐름이 선형적이라 ASCII로 충분히 명확함)

위 코드 블록이 데이터 흐름의 텍스트 표현입니다.

## Unit Boundary Consistency Check

- Unit 1(data-pipeline)은 Unit 2/3의 어떤 컴포넌트도 참조하지 않음 (순수 수집/저장) — 빌드 순서(Unit1 → Unit2 → Unit3)와 일치
- Unit 2(analytics-backtest)는 Unit 1의 DataStore만 참조 — 일치
- Unit 3(api-service)는 Unit 1, 2 전체를 오케스트레이션 — 일치 (마지막에 빌드되므로 문제 없음)
