# NFR Requirements Plan — Unit 3: api-service

## Plan
- [x] Generate `nfr-requirements.md`
- [x] Generate `tech-stack-decisions.md`

## Question Category Evaluation

| 카테고리 | 결정 | 근거 |
|---|---|---|
| Scalability | N/A | 이미 확정 |
| Performance | `POST /run`은 동기 처리, Unit 1/2의 soft target(수 분 내) 그대로 상속 | Functional Design BR8에서 이미 동기로 결정 |
| Availability | N/A | 이미 확정 |
| Security | SECURITY-05 입력 검증(엔드포인트가 파라미터를 거의 받지 않아 표면적 작음), SECURITY-09 하드닝(에러 응답에 스택트레이스 미노출), SECURITY-12(웹훅 URL은 `.env`, 이미 확정), SECURITY-15(전역 예외 핸들러). SECURITY-08(인증)은 요구사항 분석에서 이미 예외 처리됨. SECURITY-11(레이트리밋)은 비공개 API라 N/A | 요구사항 분석/이전 유닛 결정과 일관되게 적용 |
| Tech Stack | FastAPI, uvicorn, APScheduler — 사용자 지정 그대로 | 재확인만 |
| Reliability | APScheduler `coalesce=True, misfire_grace_time=300`(5분) — 서버가 잠깐 멈췄다 켜져도 밀린 실행을 여러 번 몰아서 하지 않고 1회로 합침. Unit 3 자체 락(Functional Design BR2)으로 중복 실행 방지 | 스케줄러의 놓친 트리거를 무한정 쌓아 실행하면 오히려 위험 — 안전한 기본값 |
| Maintainability | 표준 `logging`, `TestClient`(FastAPI 내장, httpx 기반)로 API 테스트 | 신규 라이브러리 불필요 (FastAPI에 포함) |

질문 없이 바로 산출물을 생성합니다.
