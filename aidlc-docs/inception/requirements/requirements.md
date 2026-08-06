# Requirements — Docker Compose 인프라 + 업비트 Open API 사용 여부 확인

## Intent Analysis Summary
- **User Request**: "Using AI-DLC 서비스 띄우기 위한 인프라 환경은 docker-compose로 만들어줘. 그리고 업비트 open api 사용 가능한 형태인거야? 맞다면 api 키는 실행 단계에서 vm option으로 입력 받아서 처리될 수 있도록 해줘."
- **Request Type**: Enhancement (infra addition to an already-delivered project) + clarification question about existing integration
- **Scope Estimate**: Single component (deployment/infra for the existing single-process FastAPI app) — no new business logic, no new units
- **Complexity Estimate**: Simple — one service, no external dependencies (DB is SQLite, no message queue/cache/second service)
- **Depth Applied**: Minimal/Standard (per requirements-analysis.md Step 3) — clear request, but with one genuine ambiguity (whether to add unused Upbit auth-key plumbing) requiring clarification before implementation

## Code Investigation Findings
`src/upbit_client.py` uses only `pyupbit`'s public/unauthenticated surface:
- `pyupbit.get_ohlcv(...)` — public candle data
- `pyupbit.get_tickers(fiat="KRW")` + public `GET https://api.upbit.com/v1/ticker` — public ticker data

No `access_key`/`secret_key`, no authenticated Upbit Open API calls (orders, account balance, etc.) exist anywhere in `src/`. `src/config.py` has no Upbit-related settings at all today — only `telegram_bot_token`, `telegram_chat_id`, `discord_webhook_url` are secrets, sourced from `.env` (gitignored) and never from `config/settings.yaml`.

**Answer to the user's question**: The current codebase is *not* in a form that uses the authenticated Upbit Open API — it only calls Upbit's public market-data endpoints, which require no API key.

## Clarifying Answers (from requirement-verification-questions.md)
| # | Question | Answer |
|---|---|---|
| 1 | docker-compose 목적 | 서버(VM)에서 상시 운영 (프로덕션 관례 적용). 배포 자동화(CI/CD)는 불필요 — 수동 이미지 빌드 후 `docker-compose up`. |
| 2 | SQLite 영속성 | 호스트 `./data` 디렉토리 바인드 마운트 (기존 `db_path` 설정 그대로) |
| 3 | 업비트 인증 키 처리 | 현재 코드가 인증 API를 쓰지 않으므로 추가 작업 없이 그대로 둔다— 미사용 설정을 미리 만들지 않음 |
| 4 | "VM option" 구현 방식 | 다른 방식 희망: 로컬(비-컨테이너) 실행 시에는 IntelliJ Run Configuration의 환경 변수로 입력 |

## Functional Requirements
- FR-I1: `docker-compose.yml`로 기존 FastAPI 앱(`uvicorn src.api:app`, in-process APScheduler 포함)을 컨테이너 하나로 띄울 수 있어야 한다.
- FR-I2: SQLite DB 파일이 컨테이너 재생성 후에도 유지되어야 한다 (호스트 `./data` 바인드 마운트).
- FR-I3: 기존 시크릿(`TELEGRAM_BOT_TOKEN`, `TELEGRAM_CHAT_ID`, `DISCORD_WEBHOOK_URL`)은 이미지에 포함되지 않고, 실행 시점에 `.env` 파일(커밋 안 됨, 기존 관례 그대로)을 통해 컨테이너에 주입되어야 한다.
- FR-I4: 업비트 API 키 관련 코드/설정은 추가하지 않는다 (현재 미사용, Q3 답변에 따름).

## Non-Functional Requirements (Infra)
- NFR-I1 (Security, SECURITY-12 연장): 시크릿은 이미지 레이어에 절대 포함되지 않는다 — `.dockerignore`로 `.env` 제외, `env_file`/환경변수로만 주입.
- NFR-I2 (Security): Dockerfile은 pinned base image tag 사용 (`latest` 금지, 기존 SECURITY 규칙과 동일).
- NFR-I3 (Security): 컨테이너는 non-root 사용자로 실행.
- NFR-I4 (Resiliency, RESILIENCY-06 연장): docker-compose의 `healthcheck`가 기존 `GET /health` 엔드포인트를 사용해 컨테이너 상태를 반영한다.
- NFR-I5 (Operability, Q1 답변 반영): 상시 운영 목적이므로 `restart: unless-stopped` 적용.

## Out of Scope (explicit, per Q3/Q4 answers)
- Upbit 인증 API 키(`access_key`/`secret_key`) 설정 추가 — 코드에서 사용하지 않으므로 만들지 않음.
- CI/CD 파이프라인, 멀티 스테이지 배포 자동화 — Q1 답변에서 명시적으로 불필요.
- 클라우드/오케스트레이션(K8s 등), 로드밸런서, 메시징 인프라 — 기존 NFR Design 결정("no cloud infra, local single instance")과 동일하게 해당 없음, 단일 컨테이너로 충분.
