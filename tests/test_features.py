from datetime import datetime, timedelta, timezone

import numpy as np
import pandas as pd
from hypothesis import given, settings
from hypothesis import strategies as st

from src.data_store import Candle
from src.features import IchimokuPoint, as_of, compute_ichimoku, is_bullish
from tests.ichimoku_reference import reference_ichimoku


def make_candles(n: int, seed: int = 42) -> list[Candle]:
    rng = np.random.default_rng(seed)
    close = 100 + np.cumsum(rng.standard_normal(n))
    high = close + rng.random(n) * 2
    low = close - rng.random(n) * 2
    start = datetime(2024, 1, 1, tzinfo=timezone.utc)
    return [
        Candle(
            market="KRW-XRP",
            timeframe="1h",
            candle_time=start + timedelta(hours=i),
            open=float(close[i]),
            high=float(high[i]),
            low=float(low[i]),
            close=float(close[i]),
            volume=1000.0,
        )
        for i in range(n)
    ]


# --- Oracle test (PBT-05 style, advisory but run for correctness assurance) ---

def test_compute_ichimoku_matches_pure_pandas_reference():
    candles = make_candles(200)
    points = compute_ichimoku(candles)

    df = pd.DataFrame(
        {
            "high": [c.high for c in candles],
            "low": [c.low for c in candles],
            "close": [c.close for c in candles],
        }
    )
    reference = reference_ichimoku(df["high"], df["low"], df["close"])

    for i, point in enumerate(points):
        ref_row = reference.iloc[i]
        assert _approx_equal(point.tenkan, ref_row["tenkan"])
        assert _approx_equal(point.kijun, ref_row["kijun"])
        assert _approx_equal(point.senkou_a, ref_row["senkou_a"])
        assert _approx_equal(point.senkou_b, ref_row["senkou_b"])


def _approx_equal(a, b, tol=1e-6):
    a_is_nan = a is None or (isinstance(a, float) and pd.isna(a))
    b_is_nan = b is None or pd.isna(b)
    if a_is_nan or b_is_nan:
        return a_is_nan == b_is_nan
    return abs(a - b) < tol


# --- Warmup boundary tests ---

def test_kijun_is_none_when_insufficient_history():
    candles = make_candles(20)  # < 26
    points = compute_ichimoku(candles)
    assert all(p.kijun is None for p in points)


def test_senkou_b_is_none_when_insufficient_history():
    # senkou_b needs a 52-period window shifted by 25 -> first valid at index 76 (empirically verified)
    candles = make_candles(75)
    points = compute_ichimoku(candles)
    assert all(p.senkou_b is None for p in points)


def test_senkou_a_becomes_available_once_kijun_and_shift_satisfied():
    # senkou_a needs kijun (26-period, valid from index 25) shifted by 25 -> first valid at index 50
    candles = make_candles(60)
    points = compute_ichimoku(candles)
    assert all(p.senkou_a is None for p in points[:50])
    assert all(p.senkou_a is not None for p in points[50:])


def test_empty_candles_returns_empty_list():
    assert compute_ichimoku([]) == []


# --- is_bullish (PBT-03 invariant) ---

@settings(deadline=None)
@given(
    close=st.floats(min_value=1, max_value=10_000, allow_nan=False),
    senkou_a=st.floats(min_value=1, max_value=10_000, allow_nan=False),
    senkou_b=st.floats(min_value=1, max_value=10_000, allow_nan=False),
)
def test_pbt_is_bullish_matches_definition(close, senkou_a, senkou_b):
    point = IchimokuPoint(
        candle_time=datetime(2024, 1, 1, tzinfo=timezone.utc),
        close=close,
        tenkan=None,
        kijun=None,
        senkou_a=senkou_a,
        senkou_b=senkou_b,
    )
    expected = (close > max(senkou_a, senkou_b)) and (senkou_a > senkou_b)
    assert is_bullish(point) == expected


def test_is_bullish_false_when_senkou_missing():
    point = IchimokuPoint(datetime(2024, 1, 1, tzinfo=timezone.utc), 100.0, None, None, None, None)
    assert is_bullish(point) is False


# --- as_of ---

def _point_at(hour: int) -> IchimokuPoint:
    return IchimokuPoint(
        candle_time=datetime(2024, 1, 1, tzinfo=timezone.utc) + timedelta(hours=hour),
        close=100.0,
        tenkan=1.0,
        kijun=1.0,
        senkou_a=1.0,
        senkou_b=1.0,
    )


def test_as_of_returns_most_recent_point_at_or_before_timestamp():
    points_4h = [_point_at(0), _point_at(4), _point_at(8)]
    result = as_of(points_4h, datetime(2024, 1, 1, tzinfo=timezone.utc) + timedelta(hours=5))
    assert result.candle_time == points_4h[1].candle_time


def test_as_of_returns_none_when_timestamp_before_first_point():
    points_4h = [_point_at(4), _point_at(8)]
    result = as_of(points_4h, datetime(2024, 1, 1, tzinfo=timezone.utc))
    assert result is None


def test_as_of_returns_exact_match():
    points_4h = [_point_at(0), _point_at(4)]
    result = as_of(points_4h, points_4h[1].candle_time)
    assert result.candle_time == points_4h[1].candle_time
