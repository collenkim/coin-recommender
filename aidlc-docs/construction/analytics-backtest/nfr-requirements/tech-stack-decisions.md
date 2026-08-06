# Tech Stack Decisions — Unit 2: analytics-backtest

| 기술 | 용도 | 비고 |
|---|---|---|
| pandas | 벡터화 캔들/지표 연산 | 사용자 지정 |
| pandas-ta | 일목균형표(`ichimoku()`) 계산 | 사용자 지정. 출력은 오라클 테스트로 BR1 정렬 규칙과의 일치 여부 검증 |
| numpy | pandas-ta 미사용 참조 구현(오라클 테스트용) | pandas의 전이 의존성, 신규 도입 아님 |
| Hypothesis | PBT-03 불변식 테스트 | Requirements Analysis에서 확정 |

신규로 추가 도입하는 라이브러리 없음 — `requirements.txt`에 `pandas-ta` 추가만 필요 (Unit 1에는 없었음).
