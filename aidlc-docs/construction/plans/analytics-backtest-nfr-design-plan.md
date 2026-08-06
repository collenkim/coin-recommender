# NFR Design Plan — Unit 2: analytics-backtest

## Plan
- [x] Generate `nfr-design-patterns.md`
- [x] Generate `logical-components.md`

## Question Category Evaluation

| 카테고리 | 결정 | 근거 |
|---|---|---|
| Resilience Patterns | 이력 부족 코인은 조용히 스킵 (예외 없음), 외부 호출 없어 재시도 불필요 | 이미 NFR Requirements에서 확정 |
| Scalability Patterns | N/A | 이미 확정 |
| Performance Patterns | `pandas-ta.ichimoku()` + rolling/vectorized 연산, 코인당 1회씩만 계산(재계산 없음) | business-logic-model.md의 단일 패스 설계가 이미 재계산을 피함 |
| Security Patterns | N/A | 외부 호출/시크릿 없음 |
| Logical Components | 오라클 참조 구현은 `tests/ichimoku_reference.py`(테스트 전용, 프로덕션 코드 아님)에 배치. `as_of_4h` 매칭 유틸은 `features.py` 내부 함수로 배치 (1h/4h 정렬은 지표 계산과 밀접) | 프로덕션 코드가 두 가지 구현을 갖지 않도록 참조 구현은 테스트 영역에만 존재해야 함 |

질문 없이 바로 산출물을 생성합니다.
