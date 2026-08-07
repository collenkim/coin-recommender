# Code Generation Plan — Unit 2: analytics-backtest (추천 결과 사후 판별)

Story: 추천 결과 적중 판별 및 학습 반영 (BR11, BR12)

- [x] Step 1: `src/backtest.py`에 `RecommendationOutcome` dataclass 추가
- [x] Step 2: `src/backtest.py`에 `evaluate_outcome(market, run_time, candles_1h)` 함수 추가 (BR11)
- [x] Step 3: 단위 테스트 (`tests/test_backtest.py`) — 정상 판별(적중/미적중), 데이터 부족(entry 없음/window 부족) → None
