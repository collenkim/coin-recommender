# Business Logic Model — Unit 1: data-pipeline

## 1. 후보군 선정 (MarketSelector)

1. 업비트 전체 KRW 마켓의 24시간 누적 거래대금(`trade_price_24h`) 조회
2. BTC, ETH 마켓 제외
3. 거래대금 내림차순 정렬 후 상위 20개 선택
4. 매 실행마다 새로 계산 (고정 리스트 캐시 없음)

## 2. 캔들 수집 흐름 (UpbitClient / BinanceClient + DataStore)

각 (market, timeframe) 조합마다:

```
IF DataStore.get_last_candle_time(source, market, timeframe) is None:
    # 최초 실행 — 부트스트랩
    지표용: 최소 100봉 수집
    백테스트용: backtest_lookback_days(기본 180일)에 해당하는 캔들 추가 수집
    (두 수집 모두 같은 upsert 대상이므로 겹치는 구간은 자연히 중복 제거됨)
    IF 수집된 캔들 수 < 100:
        해당 (market, timeframe)은 이번 회차 후보에서 제외 (CollectionResult.status = "skipped_insufficient_history")
        다음 (market, timeframe)으로 계속 진행
ELSE:
    # 증분 수집
    last_time = DataStore.get_last_candle_time(source, market, timeframe)
    last_time 이후 캔들만 조회
DataStore.upsert_candles(source, market, timeframe, candles)
```

## 3. Binance 참고 데이터 수집

BTC, ETH 각각에 대해 동일한 부트스트랩/증분 로직을 4시간봉에만 적용 (Binance는 레짐 참고용, 1시간봉 불필요).

## 4. 실행 순서 (Unit 1이 Pipeline에 노출하는 진입점)

```
1. candidates = MarketSelector.get_candidate_markets()
2. FOR market IN candidates:
     FOR timeframe IN [1h, 4h]:
       수집 흐름(섹션 2) 실행
3. FOR symbol IN [BTCUSDT, ETHUSDT]:
     수집 흐름(섹션 2, timeframe=4h) 실행
4. 최종 후보 리스트 반환 (섹션 2에서 제외된 마켓은 제외됨)
```

## Testable Properties (PBT-01, advisory — PBT는 부분 적용이라 이 유닛에서는 참고용)

| 대상 | 속성 유형 | 설명 |
|---|---|---|
| `DataStore.upsert_candles` → `DataStore.get_candles` | Round-trip (PBT-02, 적용대상) | 저장한 캔들을 그대로 조회했을 때 동일해야 함 |
| `DataStore.upsert_candles` (동일 캔들 재삽입) | Idempotence | 같은 (source, market, timeframe, candle_time)로 두 번 upsert해도 결과가 1회와 동일 |
