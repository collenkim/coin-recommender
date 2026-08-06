# Domain Entities — Unit 1: data-pipeline

## Candle
캔들 1개 (OHLCV)

| Field | Type | 설명 |
|---|---|---|
| source | "upbit" \| "binance" | 데이터 출처 |
| market | str | 마켓 코드 (예: "KRW-XRP", "BTCUSDT") |
| timeframe | "1h" \| "4h" | 캔들 주기 |
| candle_time | datetime (UTC) | 캔들 시작 시각, UTC 정규화 |
| open, high, low, close | float | OHLC |
| volume | float | 거래량 |

**Business Key**: (source, market, timeframe, candle_time) — 유니크, upsert 기준

## TickerInfo
후보군 선정을 위한 24시간 거래 정보 (MarketSelector가 사용, 저장 대상 아님 — 휘발성 조회 결과)

| Field | Type | 설명 |
|---|---|---|
| market | str | 마켓 코드 |
| trade_price_24h | float | 24시간 누적 거래대금 |

## CollectionResult
1회 수집 실행의 결과 요약 (파이프라인 로깅/부분 실패 추적용)

| Field | Type | 설명 |
|---|---|---|
| market | str | 대상 마켓 |
| timeframe | str | 대상 타임프레임 |
| status | "ok" \| "skipped_insufficient_history" \| "failed" | 수집 결과 상태 |
| candles_upserted | int | upsert된 캔들 수 |
