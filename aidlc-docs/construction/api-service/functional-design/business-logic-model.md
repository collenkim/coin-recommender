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

        RETURN PipelineRunResult(now, regime_bullish, recommendations)
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
GET /recommendations:
    latest = DataStore.get_latest_run()
    RETURN latest or empty response (BR6)

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
