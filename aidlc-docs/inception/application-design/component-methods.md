# Component Methods — coin-recommender

메서드 시그니처와 목적만 정의합니다. 상세 비즈니스 규칙(정확한 계산식, 엣지케이스 처리)은 각 유닛의 Functional Design에서 정의합니다.

## Unit 1: data-pipeline

### MarketSelector
- `get_candidate_markets() -> list[str]`
  목적: 업비트 KRW 마켓 중 24h 거래대금 상위 20개 알트코인(BTC/ETH 제외) 코드 리스트 반환

### UpbitClient
- `get_ohlcv(market: str, timeframe: str, count: int, to: datetime | None = None) -> list[Candle]`
  목적: 지정 마켓/타임프레임 캔들 조회 (부트스트랩·증분 수집 공용)
- `get_tickers_by_volume() -> list[TickerInfo]`
  목적: 전체 KRW 마켓의 24h 거래대금 조회 (MarketSelector가 사용)

### BinanceClient
- `get_klines(symbol: str, interval: str, start_time: datetime | None = None, limit: int = 100) -> list[Candle]`
  목적: 바이낸스 공개 API에서 원시 캔들 조회 (해석 없음)

### DataStore
- `upsert_candles(source: Literal["upbit", "binance"], market: str, timeframe: str, candles: list[Candle]) -> int`
  목적: (market, timeframe, candle_time) 유니크 키로 upsert, 반환값은 upsert된 행 수
- `get_last_candle_time(source: Literal["upbit", "binance"], market: str, timeframe: str) -> datetime | None`
  목적: 증분 수집 기준점 조회
- `get_candles(source: Literal["upbit", "binance"], market: str, timeframe: str, since: datetime | None = None, limit: int | None = None) -> list[Candle]`
  목적: 저장된 캔들 조회 (지표 계산·백테스트 입력용)

## Unit 2: analytics-backtest

### Features
- `compute_ichimoku(candles: list[Candle]) -> list[IchimokuPoint]`
  목적: 전환선/기준선/스팬A/스팬B/후행스팬 계산, 캔들과 동일 길이(워밍업 구간은 None) 반환

### Backtest
- `compute_signal_stats(market: str, signal_state: SignalState, candles_with_indicators: list[IchimokuPoint]) -> SignalStats`
  목적: 코인별 동일 시그널 상태의 과거 발생 시점 → 실제 24h 후 수익률 평균(N, 적중횟수 포함) 산출

### Scorer
- `check_market_regime(binance_btc_candles: list[Candle], binance_eth_candles: list[Candle]) -> bool`
  목적: BTC/ETH 4h 구름대가 "위+양운" 조건을 만족하는지 판정 (레짐 하드필터 게이트)
- `evaluate_signal(market: str, candles_1h: list[IchimokuPoint], candles_4h: list[IchimokuPoint]) -> SignalState | None`
  목적: 현재 시점 4h 추세필터 + 1h 골든크로스 여부로 시그널 상태 판정, 미충족 시 None
- `generate_recommendations() -> list[Recommendation]`
  목적: 레짐 확인 → 후보별 시그널 판정 → 기대수익률 조회 → 4% 필터링까지 전체 스코어링 실행

## Unit 3: api-service

### Pipeline
- `run_recommendation_pipeline() -> PipelineRunResult`
  목적: 전체 파이프라인 1회 실행 (수집 → 저장 → 스코어링 → 알림), `POST /run`과 Scheduler가 공유 호출

### Scheduler
- `start_scheduler(app: FastAPI) -> None`
  목적: lifespan에서 APScheduler 시작, 매시 정각+5분 잡 등록
- `stop_scheduler() -> None`
  목적: lifespan 종료 시 스케줄러 정지

### Notifier
- `send_notification(recommendations: list[Recommendation]) -> None`
  목적: 텔레그램/디스코드 웹훅 전송 (0개여도 "추천 없음" 메시지 전송)

### API
- `GET /recommendations -> RecommendationResponse`
  목적: 최신 실행의 추천 리스트 반환
- `POST /run -> PipelineRunResult`
  목적: 수동으로 Pipeline 1회 실행
- `GET /health -> HealthStatus`
  목적: 프로세스 및 DB 연결 상태 확인 (RESILIENCY-06)
