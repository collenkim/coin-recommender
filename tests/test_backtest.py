from datetime import datetime, timedelta, timezone

from hypothesis import given, settings
from hypothesis import strategies as st

from src.backtest import aggregate_stats, compute_signal_stats, golden_cross_event
from src.features import IchimokuPoint

UTC = timezone.utc
T0 = datetime(2024, 1, 1, tzinfo=UTC)


def point(hour, close=100.0, tenkan=None, kijun=None, senkou_a=None, senkou_b=None) -> IchimokuPoint:
    return IchimokuPoint(
        candle_time=T0 + timedelta(hours=hour),
        close=close,
        tenkan=tenkan,
        kijun=kijun,
        senkou_a=senkou_a,
        senkou_b=senkou_b,
    )


# --- golden_cross_event ---

def test_golden_cross_event_true_on_exact_crossover_bar():
    points = [point(0, tenkan=9, kijun=10), point(1, tenkan=11, kijun=10)]
    assert golden_cross_event(points, 1) is True


def test_golden_cross_event_false_when_already_above():
    points = [point(0, tenkan=11, kijun=10), point(1, tenkan=12, kijun=10)]
    assert golden_cross_event(points, 1) is False


def test_golden_cross_event_false_at_index_zero():
    points = [point(0, tenkan=11, kijun=10)]
    assert golden_cross_event(points, 0) is False


def test_golden_cross_event_false_when_indicators_missing():
    points = [point(0, tenkan=None, kijun=None), point(1, tenkan=11, kijun=10)]
    assert golden_cross_event(points, 1) is False


# --- compute_signal_stats (integration of BR6/BR7/BR8) ---

def _bullish_4h_series(hours: list[int]) -> list[IchimokuPoint]:
    return [point(h, close=100.0, senkou_a=10.0, senkou_b=5.0) for h in hours]


def test_compute_signal_stats_counts_valid_historical_signal():
    # Golden cross at hour=10 (bar index 10), 4h trend bullish, regime bullish, far enough in the past.
    points_1h = [point(h, tenkan=9, kijun=10) for h in range(0, 10)]
    points_1h.append(point(10, close=100.0, tenkan=11, kijun=10))  # cross event here
    points_1h += [point(h, close=100.0 + h) for h in range(11, 40)]  # need i+24 to exist
    points_1h[10 + 24] = point(10 + 24, close=106.0, tenkan=1, kijun=1)  # +6% forward return

    points_4h = _bullish_4h_series(list(range(0, 40, 4)))
    btc = _bullish_4h_series(list(range(0, 40, 4)))
    eth = _bullish_4h_series(list(range(0, 40, 4)))

    now = T0 + timedelta(hours=100)  # far enough that hour=10 signal is > 24h old

    stats = compute_signal_stats("KRW-XRP", points_1h, points_4h, btc, eth, now)

    assert stats.n == 1
    assert stats.expected_return is not None
    assert abs(stats.expected_return - 0.06) < 1e-9
    assert stats.hit_count == 1


def test_compute_signal_stats_excludes_signal_within_last_24h():
    points_1h = [point(h, tenkan=9, kijun=10) for h in range(0, 10)]
    points_1h.append(point(10, tenkan=11, kijun=10))
    points_1h += [point(h) for h in range(11, 40)]

    points_4h = _bullish_4h_series(list(range(0, 40, 4)))
    now = T0 + timedelta(hours=15)  # signal at hour 10 is only 5h old -> excluded

    stats = compute_signal_stats("KRW-XRP", points_1h, points_4h, points_4h, points_4h, now)

    assert stats.n == 0
    assert stats.expected_return is None


def test_compute_signal_stats_excludes_when_regime_not_bullish():
    points_1h = [point(h, tenkan=9, kijun=10) for h in range(0, 10)]
    points_1h.append(point(10, tenkan=11, kijun=10))
    points_1h += [point(h) for h in range(11, 40)]

    points_4h = _bullish_4h_series(list(range(0, 40, 4)))
    bearish_regime = [point(h, close=1.0, senkou_a=5.0, senkou_b=10.0) for h in range(0, 40, 4)]  # not bullish
    now = T0 + timedelta(hours=100)

    stats = compute_signal_stats("KRW-XRP", points_1h, points_4h, bearish_regime, points_4h, now)

    assert stats.n == 0


def test_compute_signal_stats_excludes_when_coin_4h_trend_fails():
    points_1h = [point(h, tenkan=9, kijun=10) for h in range(0, 10)]
    points_1h.append(point(10, tenkan=11, kijun=10))
    points_1h += [point(h) for h in range(11, 40)]

    bearish_4h = [point(h, close=1.0, senkou_a=5.0, senkou_b=10.0) for h in range(0, 40, 4)]
    bullish_regime = _bullish_4h_series(list(range(0, 40, 4)))
    now = T0 + timedelta(hours=100)

    stats = compute_signal_stats("KRW-XRP", points_1h, bearish_4h, bullish_regime, bullish_regime, now)

    assert stats.n == 0


# --- aggregate_stats (PBT-03 invariants) ---

@settings(deadline=None)
@given(samples=st.lists(st.floats(min_value=-0.5, max_value=0.5, allow_nan=False), max_size=50))
def test_pbt_hit_count_never_exceeds_n(samples):
    stats = aggregate_stats("KRW-XRP", samples)
    assert stats.hit_count <= stats.n
    assert stats.n == len(samples)


def test_aggregate_stats_empty_samples_yields_none_expected_return():
    stats = aggregate_stats("KRW-XRP", [])
    assert stats.n == 0
    assert stats.expected_return is None
    assert stats.hit_count == 0


@settings(deadline=None)
@given(samples=st.lists(st.floats(min_value=-0.5, max_value=0.5, allow_nan=False), min_size=1, max_size=50))
def test_pbt_expected_return_is_mean_of_samples(samples):
    stats = aggregate_stats("KRW-XRP", samples)
    assert abs(stats.expected_return - (sum(samples) / len(samples))) < 1e-9
