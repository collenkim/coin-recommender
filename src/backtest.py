from dataclasses import dataclass
from datetime import datetime, timedelta

from src.data_store import Candle
from src.features import IchimokuPoint, as_of, is_bullish

EXPECTED_RETURN_THRESHOLD = 0.04
FORWARD_BARS_1H = 24  # 24h forward return on 1h candles
GOLDEN_CROSS_LOOKBACK_BARS = 3  # BR4: how many bars a golden cross stays actionable
MIN_SIGNAL_SAMPLES = 3  # BR15: distinct past crossovers required before a coin may be recommended


@dataclass(frozen=True)
class SignalStats:
    market: str
    expected_return: float | None
    n: int
    hit_count: int
    max_drawdown: float | None = None  # worst intra-window dip across past samples (negative), BR16


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


def golden_cross_within(points_1h: list[IchimokuPoint], i: int, lookback: int = GOLDEN_CROSS_LOOKBACK_BARS) -> bool:
    """BR4: True if a golden cross fired on bar `i` or within the `lookback - 1` bars before it.

    Requiring the cross on the exact evaluated bar made the strategy fire once every ~103h (7
    opportunities per 30 days of stored candles); a 3-bar window gives 10, because a cross whose
    trend/regime confirmation only lands an hour or two later is no longer discarded. Quality is
    preserved rather than traded away: the 4h trend (BR3) and BTC/ETH regime (BR5) are still
    evaluated at the *entry* bar, so the extra bars act as confirmation.
    """
    return any(golden_cross_event(points_1h, j) for j in range(max(0, i - lookback + 1), i + 1))


def _last_cross_bar(points_1h: list[IchimokuPoint], i: int, lookback: int = GOLDEN_CROSS_LOOKBACK_BARS) -> int | None:
    """Index of the crossover that makes bar `i` actionable -- the dedup key for BR8 sampling.
    Crossovers can never occur on consecutive bars (a cross leaves tenkan above kijun, so the next
    bar fails the `prev.tenkan <= prev.kijun` leg), so this maps each entry bar to exactly one event."""
    for j in range(i, max(0, i - lookback + 1) - 1, -1):
        if golden_cross_event(points_1h, j):
            return j
    return None


def _composite_signal(points_1h: list[IchimokuPoint], points_4h: list[IchimokuPoint], i: int) -> bool:
    """BR6: a recent golden cross (BR4) AND the coin's own 4h trend filter passes as-of this bar's time."""
    if not golden_cross_within(points_1h, i):
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
    candles_1h: list[Candle] | None = None,
) -> SignalStats:
    """BR8: scan the coin's full 1h history for past composite-signal occurrences that were also
    regime-bullish at the time, excluding occurrences too recent to have an observed 24h outcome.

    Each sample is measured from the bar we would actually have entered on, which is the same bar
    the live check evaluates (scorer._composite_signal_on_latest_bar) -- so expected_return describes
    the entry the recommendation actually offers.

    One sample per crossover (BR8 dedup): the BR4 window makes up to GOLDEN_CROSS_LOOKBACK_BARS
    consecutive bars actionable off a single cross, and counting each of them separately both
    inflated `n` ~3x and *biased expected_return*, because a cross whose trend/regime held for three
    bars silently got three times the weight of one that held for a single bar. Measured on real
    data that flipped KRW-ONDO from -0.88% to +2.32%. Sampling only the first qualifying bar per
    crossover makes `n` a count of independent events and removes the weighting bias."""
    samples: list[float] = []
    drawdowns: list[float] = []
    sampled_crosses: set[int] = set()
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

        cross_bar = _last_cross_bar(points_1h, i)
        if cross_bar is None or cross_bar in sampled_crosses:
            continue
        sampled_crosses.add(cross_bar)

        entry_close = points_1h[i].close
        exit_close = points_1h[i + FORWARD_BARS_1H].close
        samples.append((exit_close - entry_close) / entry_close)

        # BR16: raw candles carry the lows that IchimokuPoint does not, and they are index-aligned
        # with points_1h (compute_ichimoku maps 1:1), so the same `i` addresses both.
        if candles_1h is not None and i + FORWARD_BARS_1H < len(candles_1h):
            window = candles_1h[i + 1 : i + 1 + FORWARD_BARS_1H]
            if window:
                drawdowns.append((min(c.low for c in window) - entry_close) / entry_close)

    return aggregate_stats(market, samples, max_drawdown=min(drawdowns) if drawdowns else None)


def aggregate_stats(market: str, samples: list[float], max_drawdown: float | None = None) -> SignalStats:
    """BR8/BR9: n=0 -> expected_return is None (not computable, not zero)."""
    n = len(samples)
    expected_return = (sum(samples) / n) if n > 0 else None
    hit_count = sum(1 for r in samples if r >= EXPECTED_RETURN_THRESHOLD)
    return SignalStats(market=market, expected_return=expected_return, n=n, hit_count=hit_count, max_drawdown=max_drawdown)


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
