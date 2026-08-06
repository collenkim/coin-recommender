# NFR Design Plan — Unit 1: data-pipeline

## Plan
- [x] Generate `nfr-design-patterns.md`
- [x] Generate `logical-components.md`

## Question Category Evaluation

| 카테고리 | 결정 | 근거 |
|---|---|---|
| Resilience Patterns | 재시도 유틸(지수 백오프) + 실패 시 해당 항목 스킵. 서킷브레이커는 도입하지 않음 | 상시 트래픽이 아닌 시간당 1회 배치성 호출이라 서킷브레이커의 이점이 낮음(개인 프로젝트 규모) — NFR Requirements에서 확정한 재시도 정책으로 충분 |
| Scalability Patterns | N/A | 이미 확정 |
| Performance Patterns | 업비트 호출 사이 100ms 지연(레이트리밋 여유 확보), 바이낸스는 호출량이 적어(BTC/ETH 2건) 지연 불필요 | 업비트 공개 API 요청 제한 대응을 위한 보수적 기본값 |
| Security Patterns | DB 파일 경로는 `settings.yaml`로 설정 가능하게 (하드코딩 금지 원칙 연장) | SECURITY-09 하드닝 원칙과 일관 |
| Logical Components | SQLite WAL 저널 모드 + 작업 단위 short-lived connection (연결을 전역으로 유지하지 않음) | Unit 3의 스케줄러(백그라운드 스레드)와 API 요청이 동시에 DB에 접근할 수 있음 — WAL 모드는 동시 읽기를 허용해 락 경합을 줄임, 커넥션을 스레드 간 공유하지 않는 편이 안전 |

질문 없이 바로 산출물을 생성합니다.
