from dataclasses import dataclass
from datetime import datetime, timedelta

from src.data_store import Candle
from src.features import IchimokuPoint, as_of, is_bullish

EXPECTED_RETURN_THRESHOLD = 0.04
FORWARD_BARS_1H = 24  # 24h forward return on 1h candles


@dataclass(frozen=True)
class SignalStats:
    market: str
    expected_return: float | None
    n: int
    hit_count: int


@dataclass(frozen=True)
class RecommendationOutcome:
    market: str
    run_time: datetime
    target_reached: bool
    realized_return: float
    evaluated_at: datetime


def golden_cross_event(points_1h: list[IchimokuPoint], i: int) -> bool:
    """BR4: event-based -- True only on the exact bar where tenkan crosses above kijun."""
    if i == 0:
        return False
    prev, curr = points_1h[i - 1], points_1h[i]
    if None in (prev.tenkan, prev.kijun, curr.tenkan, curr.kijun):
        return False
    return prev.tenkan <= prev.kijun and curr.tenkan > curr.kijun


def _composite_signal(points_1h: list[IchimokuPoint], points_4h: list[IchimokuPoint], i: int) -> bool:
    """BR6: golden cross event AND the coin's own 4h trend filter passes as-of this bar's time."""
    if not golden_cross_event(points_1h, i):
        return False
    trend_point = as_of(points_4h, points_1h[i].candle_time)
    return trend_point is not None and is_bullish(trend_point)


def _regime_bullish_at(btc_points_4h: list[IchimokuPoint], eth_points_4h: list[IchimokuPoint], timestamp: datetime) -> bool:
    """BR5: BTC AND ETH must both be bullish as-of the given timestamp."""
    btc_point = as_of(btc_points_4h, timestamp)
    eth_point = as_of(eth_points_4h, timestamp)
    if btc_point is None or eth_point is None:
        return False
    return is_bullish(btc_point) and is_bullish(eth_point)


def compute_signal_stats(
    market: str,
    points_1h: list[IchimokuPoint],
    points_4h: list[IchimokuPoint],
    btc_points_4h: list[IchimokuPoint],
    eth_points_4h: list[IchimokuPoint],
    now: datetime,
) -> SignalStats:
    """BR8: scan the coin's full 1h history for past composite-signal occurrences that were also
    regime-bullish at the time, excluding occurrences too recent to have an observed 24h outcome."""
    samples: list[float] = []
    cutoff = now - timedelta(hours=FORWARD_BARS_1H)

    for i in range(len(points_1h)):
        if points_1h[i].candle_time >= cutoff:
            continue
        if i + FORWARD_BARS_1H >= len(points_1h):
            continue
        if not _composite_signal(points_1h, points_4h, i):
            continue
        if not _regime_bullish_at(btc_points_4h, eth_points_4h, points_1h[i].candle_time):
            continue

        entry_close = points_1h[i].close
        exit_close = points_1h[i + FORWARD_BARS_1H].close
        samples.append((exit_close - entry_close) / entry_close)

    return aggregate_stats(market, samples)


def aggregate_stats(market: str, samples: list[float]) -> SignalStats:
    """BR8/BR9: n=0 -> expected_return is None (not computable, not zero)."""
    n = len(samples)
    expected_return = (sum(samples) / n) if n > 0 else None
    hit_count = sum(1 for r in samples if r >= EXPECTED_RETURN_THRESHOLD)
    return SignalStats(market=market, expected_return=expected_return, n=n, hit_count=hit_count)


def evaluate_outcome(
    market: str, run_time: datetime, candles_1h: list[Candle], now: datetime
) -> RecommendationOutcome | None:
    """BR11: pure post-hoc evaluation of one past recommendation, independent of compute_signal_stats.
    Returns None when there isn't yet enough data to judge (entry candle or a full 24-bar window missing) --
    caller retries on a later run (BR12)."""
    entry_candle = None
    for candle in candles_1h:
        if candle.candle_time > run_time:
            break
        entry_candle = candle

    if entry_candle is None:
        return None

    window = [c for c in candles_1h if c.candle_time > entry_candle.candle_time][:FORWARD_BARS_1H]
    if len(window) < FORWARD_BARS_1H:
        return None

    target_reached = any(c.high >= entry_candle.close * (1 + EXPECTED_RETURN_THRESHOLD) for c in window)
    realized_return = (window[-1].close - entry_candle.close) / entry_candle.close

    return RecommendationOutcome(
        market=market,
        run_time=run_time,
        target_reached=target_reached,
        realized_return=realized_return,
        evaluated_at=now,
    )
