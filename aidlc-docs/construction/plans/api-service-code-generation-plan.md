# Code Generation Plan — Unit 3: api-service

## Unit Context
- **Requirements**: FR11(API), FR12(스케줄링), FR13(알림), FR14(인증-N/A)
- **Dependencies**: Unit 1(DataStore, 클라이언트), Unit 2(Scorer)
- **기존 파일 수정 대상**: `src/data_store.py`(신규 테이블/메서드 추가 — 기존 클래스에 in-place로 추가, 중복 파일 생성 금지), `src/config.py`(웹훅 URL 필드 추가)

## Plan

### Step 1: DataStore 확장 (`src/data_store.py` 수정)
- [x] `pipeline_runs`, `recommendations` 테이블 스키마 추가 (domain-entities.md)
- [x] `save_run(run_time, regime_bullish, recommendations)` 메서드 추가
- [x] `get_latest_run() -> PipelineRunResult | None` 메서드 추가
- [x] `ping() -> bool` 메서드 추가 (헬스체크용)

### Step 2: Config 확장 (`src/config.py` 수정)
- [x] `telegram_webhook_url: str | None`, `discord_webhook_url: str | None` 필드 추가 (`.env`에서만 로드)
- [x] `scheduler_misfire_grace_seconds: int = 300` 필드 추가

### Step 3: DataStore/Config 테스트 (기존 파일 확장)
- [x] `tests/test_data_store.py`에 `save_run`/`get_latest_run`/`ping` 테스트 추가

### Step 4: Notifier (`src/notifier.py`)
- [x] `send_notification(recommendations, run_time)` — 설정된 채널마다 발송 (BR4/BR5)

### Step 5: Notifier 테스트
- [x] `tests/test_notifier.py` — 채널 0/1/2개 조합, 메시지 포맷, 발송 실패 시 예외 전파 여부

### Step 6: Pipeline (`src/pipeline.py`)
- [x] `AlreadyRunningError`, 모듈 레벨 락
- [x] `run_recommendation_pipeline() -> PipelineRunResult` (BR1~BR3)

### Step 7: Pipeline 테스트
- [x] `tests/test_pipeline.py` — 오케스트레이션 순서(mock), 락 동작, 알림 실패해도 결과 저장됨

### Step 8: Scheduler (`src/scheduler.py`)
- [x] `start_scheduler(app)`, `stop_scheduler()`

### Step 9: API (`src/api.py`)
- [x] FastAPI 앱, lifespan(스케줄러 시작/종료)
- [x] `GET /recommendations`, `POST /run`, `GET /health`
- [x] 전역 예외 핸들러

### Step 10: API 테스트
- [x] `tests/test_api.py` — `TestClient`로 3개 엔드포인트, 중복 실행 409, 헬스체크 실패 케이스

### Step 11: Documentation Summary
- [x] `aidlc-docs/construction/api-service/code/summary.md`

### Step 12: Verify
- [x] `requirements.txt`에 `fastapi`, `uvicorn`, `apscheduler` 추가
- [x] 전체 테스트 실행 (Unit 1/2 포함 전체 회귀 확인)
- [x] `uvicorn src.api:app`로 실제 기동 확인 (가능한 범위 내에서 — 실제 거래소 API 호출 없이 헬스체크만)
