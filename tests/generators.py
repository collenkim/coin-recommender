"""Shared Hypothesis generators for domain types (PBT-07: centralized, reusable, domain-aware).

Reused across Unit 1/2/3 tests wherever a Candle (or list of candles) is needed.
"""
from datetime import datetime, timedelta, timezone

from hypothesis import strategies as st

from src.data_store import Candle

MARKET_CODES = st.sampled_from(["KRW-XRP", "KRW-DOGE", "KRW-SOL", "BTCUSDT", "ETHUSDT"])
TIMEFRAMES = st.sampled_from(["1h", "4h"])


@st.composite
def candle_strategy(draw, market=None, timeframe=None):
    """Generates a single structurally valid OHLCV Candle with high >= max(open,close) >= min(open,close) >= low."""
    open_ = draw(st.floats(min_value=0.0001, max_value=1_000_000, allow_nan=False, allow_infinity=False))
    close_ = draw(st.floats(min_value=0.0001, max_value=1_000_000, allow_nan=False, allow_infinity=False))
    high_ = draw(st.floats(min_value=max(open_, close_), max_value=max(open_, close_) * 1.1 + 1, allow_nan=False, allow_infinity=False))
    low_ = draw(st.floats(min_value=0.0001, max_value=min(open_, close_), allow_nan=False, allow_infinity=False))
    volume_ = draw(st.floats(min_value=0.0, max_value=1_000_000_000, allow_nan=False, allow_infinity=False))
    minutes_offset = draw(st.integers(min_value=0, max_value=100_000))
    candle_time = datetime(2020, 1, 1, tzinfo=timezone.utc) + timedelta(minutes=minutes_offset)

    return Candle(
        market=market if market is not None else draw(MARKET_CODES),
        timeframe=timeframe if timeframe is not None else draw(TIMEFRAMES),
        candle_time=candle_time,
        open=open_,
        high=high_,
        low=low_,
        close=close_,
        volume=volume_,
    )


def candle_list_strategy(market=None, timeframe=None, min_size=1, max_size=20):
    return st.lists(
        candle_strategy(market=market, timeframe=timeframe),
        min_size=min_size,
        max_size=max_size,
        unique_by=lambda c: c.candle_time,
    )
