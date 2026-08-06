# NFR Requirements — Unit 2: analytics-backtest

## Performance
- 모든 지표 계산(전환선/기준선/스팬)과 백테스트 스캔은 pandas 벡터화 연산(rolling, shift)으로 구현 — 행 단위 Python 반복 금지
- 전체 후보(최대 20개) x 백테스트 이력(최대 약 180일치 1시간봉 ≈ 4,300봉) 처리가 매시 실행 창 내에 완료되는 것을 목표(soft target)

## Scalability / Availability
- N/A (요구사항 분석에서 확정)

## Security
- 해당 없음 — 이 유닛은 외부 네트워크 호출이 없고(DataStore에서 저장된 데이터만 읽음) 시크릿을 다루지 않음

## Reliability
- 코인의 저장 데이터가 워밍업 기준(77봉) 미달이면 예외를 던지지 않고 해당 코인의 지표를 계산하지 않고 스킵 (Unit 1에서 이력 부족 코인이 존재할 수 있으므로 정상 케이스로 처리)
- BTC/ETH 데이터 자체가 워밍업 미달이면 레짐을 "상승 아님"으로 안전하게 처리 (하드 필터가 기본적으로 보수적으로 동작하도록)

## Tech Stack (정정 사항 — Functional Design 이후 발견)
- 프로덕션 계산에는 `pandas-ta`의 `ichimoku()`를 사용 (사용자가 요구사항에서 명시한 라이브러리)
- `pandas-ta` 출력이 business-rules.md BR1의 정렬 규칙과 실제로 일치하는지, 순수 pandas로 직접 구현한 참조 계산과 대조하는 오라클 테스트로 검증 (PBT-05 스타일, advisory — 부분 PBT 모드에서 blocking은 아니지만 정확성이 핵심이라 수행)

## Maintainability
- PBT-03(불변식) 적용 — `is_bullish`, 워밍업 구간, `compute_signal_stats`의 n/hit_count 관계
- 오라클 테스트로 `pandas-ta` 출력 검증 (advisory)
