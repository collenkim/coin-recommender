# Code Generation Plan — Unit 2: analytics-backtest

## Unit Context
- **Requirements**: FR5~FR10 (일목균형표, 추세필터, 진입시그널, 레짐필터, 기대수익률, 추천필터링)
- **Dependencies**: Unit 1 (DataStore, Candle)
- **원래 구조 대비 추가**: `tests/ichimoku_reference.py` (오라클 테스트 전용 참조 구현, 프로덕션 코드 아님 — NFR Design에서 확정)

## Plan

### Step 1: Features (`src/features.py`)
- [x] `IchimokuPoint` dataclass
- [x] `compute_ichimoku(candles) -> list[IchimokuPoint]` — `pandas-ta.ichimoku()` 래핑, BR1 정렬 규칙에 맞게 조정
- [x] `is_bullish(point) -> bool` (BR2)
- [x] `_as_of(points_4h, timestamp) -> IchimokuPoint | None` (BR6 as-of 매칭)

### Step 2: Features Testing
- [x] `tests/ichimoku_reference.py` — 순수 pandas 참조 구현 (오라클)
- [x] `tests/test_features.py` — 오라클 대조 테스트, PBT-03 불변식(워밍업, is_bullish 일관성), as-of 매칭 테스트

### Step 3: Backtest (`src/backtest.py`)
- [x] `SignalStats` dataclass
- [x] `golden_cross_event(points_1h, i) -> bool` (BR4)
- [x] `compute_signal_stats(market, points_1h, points_4h, btc_points, eth_points, now) -> SignalStats` (BR8)

### Step 4: Backtest Testing
- [x] `tests/test_backtest.py` — 예시 기반(수동 구성 시나리오) + PBT-03(n>=hit_count, n=0→None)

### Step 5: Scorer (`src/scorer.py`)
- [x] `Recommendation` dataclass
- [x] `check_market_regime(btc_points, eth_points) -> bool` (BR5, BR7-1)
- [x] `composite_signal(points_1h, points_4h, i) -> bool` (BR6)
- [x] `generate_recommendations(candidates, data_store) -> list[Recommendation]` (BR7 전체 흐름, 정렬 포함 BR10)

### Step 6: Scorer Testing
- [x] `tests/test_scorer.py` — 레짐 하드필터, 시그널 없음 스킵, 4% 미만 제외, N=0 제외, 정렬 검증

### Step 7: Documentation Summary
- [x] `aidlc-docs/construction/analytics-backtest/code/summary.md`

### Step 8: Verify
- [x] `requirements.txt`에 `pandas`, `pandas-ta` 추가
- [x] 전체 테스트 실행 (Unit 1 테스트 포함 회귀 확인)
