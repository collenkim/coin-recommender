# NFR Requirements — Unit 3: api-service

## Performance
- `POST /run`은 동기 처리, Unit 1/2의 soft target(수 분 내 완료)을 그대로 상속

## Scalability / Availability
- N/A (요구사항 분석에서 확정)

## Security
- SECURITY-05: 엔드포인트 파라미터가 거의 없어 표면적은 작지만, 향후 쿼리 파라미터 추가 시 pydantic으로 검증
- SECURITY-09: 프로덕션 에러 응답에 스택트레이스/내부 경로 미노출 (전역 예외 핸들러가 일반화된 메시지 반환)
- SECURITY-12: 웹훅 URL은 `.env`에서만 로드 (이미 확정)
- SECURITY-15: 전역 예외 핸들러 등록, 모든 외부 호출/DB 연산에 명시적 예외 처리
- SECURITY-08(인증), SECURITY-11(레이트리밋): N/A — 요구사항 분석에서 로컬/개인용으로 확정

## Reliability
- APScheduler: `coalesce=True`, `misfire_grace_time=300`(초) — 서버 다운타임 후 밀린 트리거를 여러 번 실행하지 않고 1회로 합침
- 파이프라인 중복 실행 방지: 프로세스 내 락 (Functional Design BR2)

## Maintainability
- 표준 `logging`
- `TestClient`(FastAPI 내장, httpx 기반)로 API 계층 테스트 — 신규 의존성 아님
