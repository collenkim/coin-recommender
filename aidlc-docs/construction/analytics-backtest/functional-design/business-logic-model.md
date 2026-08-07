# Business Logic Model — Unit 2: analytics-backtest

## 1. 레짐 판정 흐름 (Scorer, BR5/BR7)

```
btc_points = Features.compute_ichimoku(DataStore.get_candles("binance", "BTCUSDT", "4h"))
eth_points = Features.compute_ichimoku(DataStore.get_candles("binance", "ETHUSDT", "4h"))
latest_regime = is_bullish(btc_points[-1]) AND is_bullish(eth_points[-1])
IF NOT latest_regime:
    RETURN []  # FR8 하드 필터, 즉시 종료
```

## 2. 코인별 라이브 시그널 확인 및 백테스트 조회 (BR6, BR7, BR8)

```
FOR market IN candidates:
    candles_1h = DataStore.get_candles("upbit", market, "1h")
    candles_4h = DataStore.get_candles("upbit", market, "4h")
    points_1h = Features.compute_ichimoku(candles_1h)
    points_4h = Features.compute_ichimoku(candles_4h)

    IF NOT composite_signal(points_1h, points_4h, latest bar):
        CONTINUE  # 지금 시그널 없음, 스킵

    stats = Backtest.compute_signal_stats(
        market, points_1h, points_4h, btc_points, eth_points
    )
    IF stats.expected_return is not None AND stats.expected_return >= 0.04:
        recommendations.append(Recommendation(market, stats.expected_return, stats.n, stats.hit_count))

RETURN sorted(recommendations, key=expected_return, descending)
```

## 3. 백테스트 표본 수집 (Backtest.compute_signal_stats, BR8)

```
FOR i IN range(len(points_1h)):
    IF NOT composite_signal(points_1h, points_4h, i):
        CONTINUE
    regime_at_i = regime_bullish(as_of_4h(btc_points, eth_points, points_1h[i].candle_time))
    IF NOT regime_at_i:
        CONTINUE
    IF (now - points_1h[i].candle_time) < 24h:
        CONTINUE
    IF i + 24 >= len(points_1h):
        CONTINUE  # 24봉 뒤 데이터 자체가 없음
    forward_return = (points_1h[i+24].close - points_1h[i].close) / points_1h[i].close
    samples.append(forward_return)

RETURN SignalStats(
    market=market,
    expected_return=mean(samples) if samples else None,
    n=len(samples),
    hit_count=count(r >= 0.04 for r in samples),
)
```

## 4. 추천 결과 사후 판별 (Backtest.evaluate_outcome, BR11)

```
FUNCTION evaluate_outcome(market, run_time, candles_1h) -> RecommendationOutcome | None:
    entry_candle = 마지막으로 candle_time <= run_time 인 candles_1h 원소 (BR6과 동일한 as-of 개념, 원본 캔들 사용)
    IF entry_candle is None:
        RETURN None  # 아직 판별 불가

    window = entry_candle 이후 candle_time 순으로 최대 24개 캔들
    IF len(window) < 24:
        RETURN None  # 24봉치 데이터가 아직 안 쌓임, 다음 회차 재시도

    target_reached = ANY(c.high >= entry_candle.close * 1.04 FOR c IN window)
    realized_return = (window[-1].close - entry_candle.close) / entry_candle.close

    RETURN RecommendationOutcome(market, run_time, target_reached, realized_return, evaluated_at=now)
```

이 함수는 DataStore에 직접 접근하지 않는 순수 함수입니다 (기존 `compute_signal_stats`와 동일한 설계 원칙 — 캔들 조회는 호출자인 Unit 3가 담당).

## Testable Properties (PBT-01 identification; PBT-03은 부분 적용 대상이라 이 유닛에서 실제로 강제됨)

| 대상 | 속성 유형 | 설명 |
|---|---|---|
| `is_bullish(i)` | Invariant (PBT-03, 적용대상) | `is_bullish(i) == (above_cloud(i) and bullish_cloud(i))` — 항상 두 하위 조건의 AND와 일치해야 함 |
| `compute_ichimoku` 워밍업 구간 | Invariant (PBT-03, 적용대상) | `i < 77`인 모든 봉에서 `senkou_a`/`senkou_b`는 반드시 None |
| `compute_signal_stats` | Invariant (PBT-03, 적용대상) | `hit_count <= n` 항상 성립, `n == 0`이면 `expected_return is None` |
| `golden_cross_event` | Invariant | 연속된 두 봉이 모두 True일 수 없음 (교차는 순간적 이벤트) |
| `evaluate_outcome` | Invariant (신규) | window에 24개 미만 캔들이 있으면 항상 `None` 반환 (부분 판별 없음) |
