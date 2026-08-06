# Code Generation Summary — Unit 3: api-service

## Generated Files

### Application Code
- `src/notifier.py` — `send_notification` (텔레그램 Bot API + 디스코드 웹훅)
- `src/pipeline.py` — `run_recommendation_pipeline`, `AlreadyRunningError`, 모듈 레벨 락
- `src/scheduler.py` — `start_scheduler`, `stop_scheduler` (APScheduler, 매시 5분)
- `src/api.py` — FastAPI 앱, `GET /recommendations`, `POST /run`, `GET /health`, 전역 예외 핸들러

### 기존 파일 수정
- `src/data_store.py` — `pipeline_runs`/`recommendations` 테이블, `save_run`/`get_latest_run`/`ping` 추가
- `src/config.py` — `telegram_bot_token`, `telegram_chat_id`, `discord_webhook_url`, `scheduler_misfire_grace_seconds` 필드 추가
- `.env.example`, `README.md` 업데이트
- `requirements.txt`에 `fastapi`, `uvicorn`, `apscheduler`, `httpx`(TestClient용) 추가

### Tests (`tests/`)
- `test_data_store.py`에 5개 테스트 추가 (save_run/get_latest_run/ping)
- `test_notifier.py` — 채널 조합, 메시지 포맷, 부분 실패 (8개)
- `test_pipeline.py` — 락, 오케스트레이션, 알림 실패 격리, 부분 수집 실패 격리 (6개)
- `test_api.py` — `TestClient`로 3개 엔드포인트 전체 (7개)

## 실행 검증 (실제 실행 완료)

```
venv\Scripts\pytest -q
# 76 passed
```

**실제 서버 기동 확인**: `uvicorn src.api:app`로 실제 프로세스를 띄워 lifespan(스케줄러 시작 포함)이 정상 동작하는지, `GET /health`가 실제로 200을 반환하는지 확인 완료 (`{"status":"ok","db_connected":true}`).

## 진행 중 발견하고 고친 사항 1건

**Telegram 통합 설계 오류**: 원래 계획대로 `TELEGRAM_WEBHOOK_URL` 하나로 구현하려 했으나, Discord와 달리 **Telegram은 발신용 범용 웹훅 URL 개념이 없고** 봇 토큰(bot token) + 채팅 ID(chat id)로 Bot API의 `sendMessage` 엔드포인트를 호출해야 합니다. 그대로 진행했다면 겉보기엔 그럴듯하지만 실제로는 절대 동작하지 않는 코드가 됐을 것 — `TELEGRAM_BOT_TOKEN` + `TELEGRAM_CHAT_ID` 두 값으로 설계를 정정했습니다 (config.py, notifier.py, .env.example 반영).

## 프로젝트 전체 완료 상태

Unit 1/2/3 모두 코드 생성 완료, 총 76개 테스트 통과. 다음은 Build and Test 단계(전체 유닛 통합 빌드/테스트 지침 문서화)입니다.
