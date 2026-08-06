# Tech Stack Decisions — Unit 3: api-service

| 기술 | 용도 | 비고 |
|---|---|---|
| fastapi | REST API | 사용자 지정 |
| uvicorn | ASGI 서버 | 사용자 지정 |
| APScheduler | 인프로세스 스케줄링 | 사용자 지정 |
| requests | 텔레그램/디스코드 웹훅 POST | 사용자 지정 (Unit 1에서 이미 도입) |
| python-dotenv | `.env` 로딩 | Unit 1에서 이미 도입 (`pydantic-settings`의 `env_file`이 내부적으로 사용) |
| httpx (FastAPI TestClient 의존성) | API 테스트 | FastAPI 설치 시 함께 제공, 별도 pin 불필요 |

신규로 추가 도입하는 라이브러리 없음 — `requirements.txt`에 `fastapi`, `uvicorn`, `apscheduler` 추가만 필요.
