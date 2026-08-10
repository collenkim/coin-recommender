from datetime import datetime, timedelta, timezone

from hypothesis import given, settings
from hypothesis import strategies as st

from src.backtest import (
    GOLDEN_CROSS_LOOKBACK_BARS,
    aggregate_stats,
    compute_signal_stats,
    evaluate_outcome,
    golden_cross_event,
    golden_cross_within,
)
from src.data_store import Candle
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


def candle(hour, close=100.0, high=None) -> Candle:
    return Candle(
        market="KRW-XRP",
        timeframe="1h",
        candle_time=T0 + timedelta(hours=hour),
        open=close,
        high=high if high is not None else close,
        low=close,
        close=close,
        volume=1.0,
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


# --- golden_cross_within (BR4 window) ---

def test_golden_cross_within_true_on_the_crossover_bar_itself():
    points = [point(0, tenkan=9, kijun=10), point(1, tenkan=11, kijun=10)]
    assert golden_cross_within(points, 1) is True


CROSS_BAR = 1  # the bar the golden cross fires on in the fixtures below


def _points_with_cross_at_bar_1(total_bars: int) -> list[IchimokuPoint]:
    points = [point(0, tenkan=9, kijun=10), point(1, tenkan=11, kijun=10)]
    points += [point(h) for h in range(2, total_bars)]
    return points


def test_golden_cross_within_true_on_the_last_bar_still_inside_the_lookback():
    last_valid = CROSS_BAR + GOLDEN_CROSS_LOOKBACK_BARS - 1
    points = _points_with_cross_at_bar_1(last_valid + 2)

    assert golden_cross_within(points, last_valid) is True


def test_golden_cross_within_false_once_the_cross_falls_out_of_the_lookback():
    expired = CROSS_BAR + GOLDEN_CROSS_LOOKBACK_BARS
    points = _points_with_cross_at_bar_1(expired + 1)

    assert golden_cross_within(points, expired) is False


def test_golden_cross_within_false_when_no_cross_at_all():
    points = [point(h, tenkan=9, kijun=10) for h in range(0, 5)]
    assert golden_cross_within(points, 4) is False


# --- compute_signal_stats (integration of BR6/BR7/BR8) ---

def _bullish_4h_series(hours: list[int]) -> list[IchimokuPoint]:
    return [point(h, close=100.0, senkou_a=10.0, senkou_b=5.0) for h in hours]


def test_compute_signal_stats_takes_one_sample_per_crossover():
    """BR8 dedup: a cross at bar 10 makes bars 10..12 actionable (lookback=3), but they are the same
    event -- only the first qualifying bar is sampled, so n counts crossovers, not entry bars."""
    assert GOLDEN_CROSS_LOOKBACK_BARS == 3  # the expectations below are written for this value

    points_1h = [point(h, close=100.0, tenkan=9, kijun=10) for h in range(0, 10)]
    points_1h.append(point(10, close=100.0, tenkan=11, kijun=10))  # cross event here
    points_1h += [point(h, close=100.0) for h in range(11, 40)]  # flat; no further cross (tenkan=None)
    points_1h[34] = point(34, close=106.0)  # forward bar of entry bar 10 -> +6%
    points_1h[35] = point(35, close=100.0)  # would be entry bar 11's forward bar, must NOT be sampled
    points_1h[36] = point(36, close=100.0)  # would be entry bar 12's forward bar, must NOT be sampled

    bullish_4h = _bullish_4h_series(list(range(0, 40, 4)))
    now = T0 + timedelta(hours=100)  # far enough that the signals are > 24h old

    stats = compute_signal_stats("KRW-XRP", points_1h, bullish_4h, bullish_4h, bullish_4h, now)

    assert stats.n == 1  # one crossover -> one sample, not three
    assert abs(stats.expected_return - 0.06) < 1e-9  # the +6% entry, undiluted by its own duplicates
    assert stats.hit_count == 1


def test_compute_signal_stats_counts_two_separate_crossovers_separately():
    """Dedup must not collapse genuinely distinct events: two crossovers far apart give n == 2."""
    points_1h = [point(h, close=100.0, tenkan=9, kijun=10) for h in range(0, 10)]
    points_1h.append(point(10, close=100.0, tenkan=11, kijun=10))  # cross 1
    points_1h += [point(h, close=100.0, tenkan=9, kijun=10) for h in range(11, 20)]
    points_1h.append(point(20, close=100.0, tenkan=11, kijun=10))  # cross 2
    points_1h += [point(h, close=100.0) for h in range(21, 50)]
    points_1h[34] = point(34, close=106.0)  # cross 1 forward -> +6%
    points_1h[44] = point(44, close=100.0)  # cross 2 forward ->  0%

    bullish_4h = _bullish_4h_series(list(range(0, 50, 4)))
    now = T0 + timedelta(hours=200)

    stats = compute_signal_stats("KRW-XRP", points_1h, bullish_4h, bullish_4h, bullish_4h, now)

    assert stats.n == 2
    assert abs(stats.expected_return - 0.03) < 1e-9  # mean of +6% and 0%
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


def test_compute_signal_stats_reports_worst_drawdown_across_samples():
    """BR16: max_drawdown comes from the raw candles' lows, which IchimokuPoint does not carry."""
    points_1h = [point(h, close=100.0, tenkan=9, kijun=10) for h in range(0, 10)]
    points_1h.append(point(10, close=100.0, tenkan=11, kijun=10))  # cross -> entry bar 10
    points_1h += [point(h, close=100.0) for h in range(11, 40)]

    candles = [candle(h, close=100.0) for h in range(0, 40)]
    candles[15] = Candle("KRW-XRP", "1h", T0 + timedelta(hours=15), 100.0, 100.0, 93.0, 100.0, 1.0)  # -7% dip

    bullish_4h = _bullish_4h_series(list(range(0, 40, 4)))
    now = T0 + timedelta(hours=100)

    stats = compute_signal_stats("KRW-XRP", points_1h, bullish_4h, bullish_4h, bullish_4h, now, candles_1h=candles)

    assert stats.n == 1
    assert abs(stats.max_drawdown - (-0.07)) < 1e-9


def test_compute_signal_stats_leaves_drawdown_none_without_candles():
    points_1h = [point(h, close=100.0, tenkan=9, kijun=10) for h in range(0, 10)]
    points_1h.append(point(10, close=100.0, tenkan=11, kijun=10))
    points_1h += [point(h, close=100.0) for h in range(11, 40)]
    bullish_4h = _bullish_4h_series(list(range(0, 40, 4)))

    stats = compute_signal_stats("KRW-XRP", points_1h, bullish_4h, bullish_4h, bullish_4h, T0 + timedelta(hours=100))

    assert stats.max_drawdown is None


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


# --- evaluate_outcome (BR11) ---

def test_evaluate_outcome_target_reached_via_intra_window_high():
    run_time = T0 + timedelta(hours=10)
    candles = [candle(h, close=100.0) for h in range(0, 10)]
    candles.append(candle(10, close=100.0))  # entry candle, close=100
    window = [candle(h, close=100.0) for h in range(11, 34)]  # 23 candles, no move
    window.append(candle(34, close=100.0, high=105.0))  # 24th candle: high touches +5%, close flat
    candles += window
    now = T0 + timedelta(hours=100)

    outcome = evaluate_outcome("KRW-XRP", run_time, candles, now)

    assert outcome is not None
    assert outcome.target_reached is True  # high-based (Q1=B), even though close-based realized_return is ~0
    assert abs(outcome.realized_return - 0.0) < 1e-9
    assert outcome.evaluated_at == now


def test_evaluate_outcome_target_not_reached():
    run_time = T0 + timedelta(hours=10)
    candles = [candle(h, close=100.0) for h in range(0, 11)]
    candles += [candle(h, close=101.0, high=102.0) for h in range(11, 35)]  # +2% high, never hits +4%
    now = T0 + timedelta(hours=100)

    outcome = evaluate_outcome("KRW-XRP", run_time, candles, now)

    assert outcome is not None
    assert outcome.target_reached is False
    assert abs(outcome.realized_return - 0.01) < 1e-9


def test_evaluate_outcome_none_when_no_entry_candle_found():
    run_time = T0 - timedelta(hours=1)  # before any stored candle
    candles = [candle(h) for h in range(0, 30)]

    assert evaluate_outcome("KRW-XRP", run_time, candles, T0 + timedelta(hours=100)) is None


def test_evaluate_outcome_none_when_window_incomplete():
    run_time = T0 + timedelta(hours=10)
    candles = [candle(h) for h in range(0, 11)] + [candle(h) for h in range(11, 20)]  # only 9 bars after entry

    assert evaluate_outcome("KRW-XRP", run_time, candles, T0 + timedelta(hours=100)) is None
