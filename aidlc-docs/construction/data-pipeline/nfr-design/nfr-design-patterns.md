# NFR Design Patterns — Unit 1: data-pipeline

## Resilience: Retry with Backoff

공통 유틸 함수(예: `retry_with_backoff(fn, max_attempts=3, base_delay=1.0)`)로 업비트/바이낸스 호출을 감쌈:
- 타임아웃/연결오류/5xx → 재시도 (1s, 2s, 4s 지수 백오프)
- 4xx → 즉시 실패 (재시도 안 함)
- 최종 실패 시 예외를 상위(수집 루프)로 전달하지 않고, 해당 (market, timeframe) 항목만 `CollectionResult(status="failed")`로 기록 후 루프 계속

서킷브레이커는 도입하지 않음 — 시간당 1회 배치 호출 특성상 이점이 낮음 (RESILIENCY-10에서 "서킷브레이커는 SHOULD"이며 필수 아님).

## Performance: Rate-Limit-Aware Sequential Fetch

- 업비트 호출 사이 100ms 지연 삽입 (20 마켓 x 2 타임프레임 순회 시 레이트리밋 여유 확보)
- 바이낸스는 호출량이 적어(BTC/ETH 4h만) 지연 불필요

## Security: No Hardcoded Paths/Secrets

- SQLite DB 파일 경로는 `settings.yaml`의 설정값 사용 (하드코딩 금지)
- 이 유닛은 자격증명을 다루지 않음 (NFR Requirements에서 확정)

## Concurrency: SQLite WAL Mode + Short-Lived Connections

- DB 연결 시 `PRAGMA journal_mode=WAL` 적용 — Unit 3의 스케줄러(백그라운드 스레드)와 API 요청 스레드가 동시에 DB에 접근해도 읽기가 쓰기를 막지 않도록 함
- 커넥션은 작업 단위(함수 호출)마다 열고 닫음 — 스레드 간 커넥션 공유로 인한 `sqlite3.ProgrammingError` 방지
