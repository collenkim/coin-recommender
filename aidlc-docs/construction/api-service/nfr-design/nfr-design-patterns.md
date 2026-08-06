# NFR Design Patterns — Unit 3: api-service

## Resilience: In-Process Lock + Coalesced Scheduling

- `pipeline.py`에 모듈 레벨 `threading.Lock()` — `run_recommendation_pipeline()` 진입 시 `lock.acquire(blocking=False)` 실패하면 `AlreadyRunningError` 발생
- APScheduler: `coalesce=True, misfire_grace_time=300`

## Security: Global Exception Handler

- `api.py`에 `@app.exception_handler(Exception)` 등록 — 처리되지 않은 예외를 잡아 500 + 일반화된 메시지(`{"detail": "internal error"}`) 반환, 상세 내용은 서버 로그에만 기록 (SECURITY-09)

## Best-Effort Notification

- `Notifier.send_notification()` 호출은 `Pipeline` 내부에서 try/except로 감싸 실패해도 파이프라인 실행 자체는 성공으로 처리 (functional-design/business-rules.md BR3)
