# NFR Requirements Plan — Unit 2: analytics-backtest

## Plan
- [x] Generate `nfr-requirements.md`
- [x] Generate `tech-stack-decisions.md`

## Question Category Evaluation

| 카테고리 | 결정 | 근거 |
|---|---|---|
| Scalability | N/A | 고정 소규모 (요구사항 분석에서 확정) |
| Performance | pandas 벡터화 연산 사용 (행 단위 Python 루프 금지), 코인당 최대 ~4,300개 1시간봉(180일) x 20개 코인 백테스트 스캔이 매시 실행 창 내에 끝나야 함 | 순수 Python 루프로 20개 코인 x 4,300봉을 처리하면 느릴 수 있음 — rolling()/shift() 등 벡터화 필수 |
| Availability | N/A | 이미 확정 |
| Security | 해당 없음 — 외부 네트워크 호출 없음(DataStore에서 읽기만), 시크릿 없음 | 순수 계산 계층 |
| **Tech Stack Selection (수정 사항 발견)** | **`pandas-ta`의 `ichimoku()` 함수를 실제 계산에 사용**하되, business-rules.md BR1에서 정의한 "정렬 규칙"(미래 투영 없이 봉에 그대로 정렬)과 실제로 일치하는지 **직접 구현한 순수 pandas 참조 계산과 대조하는 오라클 테스트**로 검증 | Functional Design에서 "이 문서의 식을 코드로 직접 옮긴다"고 썼으나, 이는 사용자가 요구사항에서 명시한 `pandas-ta` 라이브러리를 쓰지 않는 셈이라 잘못된 방향이었음. 정정: 프로덕션 코드는 `pandas-ta`를 사용하고, 정확성 검증(오라클 테스트, PBT-05 스타일)에만 순수 pandas 참조 구현을 사용 |
| Reliability | 특정 코인의 저장 데이터가 부족(워밍업 미달)해도 예외 없이 해당 코인만 건너뜀 | Unit 1에서 이력 부족 코인을 스킵할 수 있으므로, Unit 2도 이를 정상 케이스로 처리해야 함 |
| Maintainability | Hypothesis(PBT-03 불변식, 이미 확정), 오라클 테스트(advisory) | - |

질문 없이 바로 산출물을 생성합니다. **Tech Stack 정정 사항**은 근거와 함께 명시했으니, 다른 방향을 원하시면 Request Changes로 알려주세요.
