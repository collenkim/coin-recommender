# NFR Design Plan — Unit 3: api-service

## Plan
- [x] Generate `nfr-design-patterns.md`
- [x] Generate `logical-components.md`

## Question Category Evaluation

| 카테고리 | 결정 | 근거 |
|---|---|---|
| Resilience Patterns | `threading.Lock` (pipeline.py 모듈 레벨), APScheduler coalesce/misfire_grace_time (이미 확정) | NFR Requirements에서 확정 |
| Scalability Patterns | N/A | 이미 확정 |
| Performance Patterns | 추가 없음 | Unit 1/2 패턴 상속 |
| Security Patterns | FastAPI 전역 예외 핸들러(`@app.exception_handler(Exception)`)로 일반화된 500 응답, 스택트레이스 미노출 | SECURITY-09/15 |
| Logical Components | Lock은 `pipeline.py`에 모듈 전역 변수로 배치 (신규 파일 불필요) | 오케스트레이션과 동시성 제어가 같은 관심사 |

질문 없이 바로 산출물을 생성합니다.
