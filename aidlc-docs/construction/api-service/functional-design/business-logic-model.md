# Business Logic Model — Unit 3: api-service

## 1. Pipeline 실행 흐름 (BR1~BR3)

```
FUNCTION run_recommendation_pipeline():
    IF lock.locked(): RAISE AlreadyRunning
    WITH lock:
        candidates = MarketSelector.get_candidate_markets()
        FOR market IN candidates: collect_and_store(market)  # Unit 1
        collect_and_store_binance(BTC); collect_and_store_binance(ETH)

        recommendations = Scorer.generate_recommendations(candidates, data_store, now)  # Unit 2
        regime_bullish = len(recommendations) > 0 OR check_market_regime(data_store)  # 저장용 참고 값

        DataStore.save_run(now, regime_bullish, recommendations)  # BR3, 항상 저장

        TRY:
            Notifier.send_notification(recommendations, now)
        EXCEPT Exception:
            log.warning(...)  # best-effort, 파이프라인 실패로 처리하지 않음

        evaluate_pending_outcomes(data_store, now)  # 신규 BR9, 같은 락 안에서 실행

        RETURN PipelineRunResult(now, regime_bullish, recommendations)
```

## 1-1. 판별 배치 흐름 (신규 — BR9)

```
FUNCTION evaluate_pending_outcomes(data_store, now):
    pending = DataStore.get_pending_evaluations(older_than=now - 24h)  # Unit 2 BR12
    FOR (market, run_time) IN pending:
        TRY:
            candles_1h = DataStore.get_candles("upbit", market, "1h")
            outcome = Backtest.evaluate_outcome(market, run_time, candles_1h)  # Unit 2 BR11
            IF outcome is not None:
                DataStore.record_outcome(outcome)
            # None이면 아직 판별 불가 -- 이번 회차는 skip, 다음 회차에 재시도
        EXCEPT Exception:
            log.warning("판별 실패: %s %s", market, run_time, exc_info=True)  # 개별 실패 격리, 나머지 계속 처리
```

## 2. Scheduler 흐름

```
lifespan(app):
    scheduler = APScheduler()
    scheduler.add_job(run_recommendation_pipeline, trigger="cron", minute=5)  # 매시 5분
    scheduler.start()
    yield
    scheduler.shutdown()
```

## 3. API 흐름

```
GET /recommendations?limit=1 (기본값):
    latest = DataStore.get_latest_run()  # 각 recommendation에 target_reached/realized_return 포함 (BR10)
    RETURN latest or empty response (BR6, 구조 100% 기존과 동일 + 신규 필드)

GET /recommendations?limit=N (N>1, 신규 BR10):
    runs = DataStore.get_recent_runs(limit=N)  # 최신 포함 최근 N회차, run_time 내림차순
    latest = runs[0]
    RETURN {run_time: latest.run_time, regime_bullish: latest.regime_bullish,
            recommendations: latest.recommendations, history: runs}

POST /run:
    TRY:
        result = run_recommendation_pipeline()
        RETURN 200, result
    EXCEPT AlreadyRunning:
        RETURN 409, {"detail": "이미 실행 중입니다"}

GET /health:
    TRY:
        DataStore.ping()
        RETURN 200, {"status": "ok", "db_connected": true}
    EXCEPT:
        RETURN 500, {"status": "error", "db_connected": false}
```

## Testable Properties (PBT-01 identification, advisory)

| 대상 | 속성 유형 | 설명 |
|---|---|---|
| `save_run` → `get_latest_run` | Round-trip (PBT-02, 적용대상) | 저장한 실행 결과를 그대로 조회 가능해야 함 |
| 알림 채널 선택 로직 | Invariant | 설정된 웹훅 URL 개수만큼만 `requests.post` 호출 (0/1/2개) |
