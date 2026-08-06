# NFR Design Patterns — Unit 2: analytics-backtest

## Performance: Vectorized Single-Pass Computation

- `pandas-ta.ichimoku()`로 지표를 한 번에 벡터화 계산 (행 단위 반복 없음)
- 각 코인의 1h/4h 지표는 `Scorer.generate_recommendations()` 1회 실행 중 정확히 1번만 계산 — 백테스트 스캔(BR8)과 라이브 시그널 확인(BR7)이 같은 계산 결과를 재사용

## Resilience: Silent Skip on Insufficient Data

- 워밍업 미달 코인은 지표가 전부 None → `composite_signal`이 자연히 False가 되어 추천에서 제외 (예외 처리 불필요, 로직 자체로 안전)
- BTC/ETH 워밍업 미달 시 레짐은 보수적으로 False 처리

## Testing: Oracle Verification (advisory, PBT-05 스타일)

`pandas-ta.ichimoku()`의 실제 출력 정렬 방식을 신뢰하지 않고, `tests/ichimoku_reference.py`의 순수 pandas 참조 구현과 대조하는 오라클 테스트를 둡니다. 불일치 시 프로덕션 코드에서 `pandas-ta` 출력을 BR1 규칙에 맞게 재정렬하는 어댑터를 추가합니다 (Code Generation 단계에서 실제 대조 후 확정).
