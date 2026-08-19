from datetime import datetime, timedelta, timezone
from unittest.mock import patch

from src.backtest import (
    BREAKOUT_BARS,
    VOLUME_BASELINE_BARS,
    FORWARD_BARS_1H,
    REBOUND,
    REGIME_BARS_30D,
    REGIME_MA_BARS,
    STOP_LOSS,
    STRONG_BULL,
    TARGET_RETURN,
    TradeOutcome,
    aggregate_stats,
    build_regime_series,
    compute_signal_stats,
    entry_signal,
    regime_as_of,
    simulate_trade,
    wilson_lower,
)
from src.data_store import Candle
from src.features import IchimokuPoint

UTC = timezone.utc
T0 = datetime(2024, 1, 1, tzinfo=UTC)


def candle(i: int, close: float, high=None, low=None, volume=100.0, timeframe="1h") -> Candle:
    return Candle(
        market="TESTUSDT",
        timeframe=timeframe,
        candle_time=T0 + timedelta(hours=i),
        open=close,
        high=close if high is None else high,
        low=close if low is None else low,
        close=close,
        volume=volume,
    )


def point(i: int, close: float, tenkan=2.0, kijun=1.0, senkou_a=0.5, senkou_b=0.4) -> IchimokuPoint:
    return IchimokuPoint(
        candle_time=T0 + timedelta(hours=i), close=close, tenkan=tenkan, kijun=kijun, senkou_a=senkou_a, senkou_b=senkou_b
    )


# --- wilson_lower (BR21) ---

def test_wilson_lower_does_not_treat_a_perfect_tiny_sample_as_certainty():
    assert wilson_lower(3, 3) < 0.50  # 3승 3패없음이라도 "확률 100%"로 읽히면 안 된다
    assert wilson_lower(20, 20) > wilson_lower(3, 3)


def test_wilson_lower_is_zero_without_samples():
    assert wilson_lower(0, 0) == 0.0


# --- build_regime_series / regime_as_of (BR20) ---

def _btc_series(closes: list[float]) -> list[Candle]:
    return [candle(i, c, timeframe="4h") for i, c in enumerate(closes)]


def test_regime_is_strong_bull_when_btc_gained_more_than_20_percent_over_30_days():
    closes = [100.0] + [100.0 + i * 0.2 for i in range(REGIME_BARS_30D)]  # 100 -> 135.8
    series = build_regime_series(_btc_series(closes))
    assert series[-1][1] == STRONG_BULL


def _rebound_closes(long_term_start: float) -> list[float]:
    """장기 구간을 `long_term_start`에서 100까지 이동시킨 뒤, 최근 30일에서 82.1까지 밀렸다가
    92.0으로 반등하는 형태. 장기 방향만 인자로 뒤집을 수 있게 만든다."""
    step = (100.0 - long_term_start) / (REGIME_MA_BARS - REGIME_BARS_30D)
    closes = [long_term_start + i * step for i in range(REGIME_MA_BARS - REGIME_BARS_30D + 1)]
    closes += [100.0 - k * 0.1 for k in range(1, REGIME_BARS_30D)]
    closes.append(92.0)
    return closes


def test_regime_is_rebound_only_inside_a_long_term_uptrend():
    """장기 상승 추세 안의 조정 후 반등."""
    series = build_regime_series(_btc_series(_rebound_closes(long_term_start=50.0)))
    assert series[-1][1] == REBOUND


def test_rebound_is_rejected_when_btc_is_below_its_200_day_average():
    """장기 하락 추세의 반등은 거짓 반등으로 보고 진입하지 않는다 -- 알트는 BTC에 끌려다니므로
    BTC가 구조적 하락 국면이면 알트가 독립적으로 오를 수 없다.

    30일 조건(수익률 음수, 저점 대비 +11%)은 위 테스트와 똑같이 만족한다. 장기 방향만 다르다."""
    series = build_regime_series(_btc_series(_rebound_closes(long_term_start=200.0)))
    assert series[-1][1] is None


def test_rebound_is_rejected_without_enough_history_to_judge_the_long_term_trend():
    closes = [100.0] + [100.0 - i * 0.1 for i in range(REGIME_BARS_30D - 1)] + [92.0]
    series = build_regime_series(_btc_series(closes))
    assert series[-1][1] is None  # 200일 이동평균을 계산할 이력이 없다


def test_strong_bull_does_not_require_the_long_term_trend_check():
    """강한 상승장은 그 자체로 추세가 확인되므로 200일선 조건을 요구하지 않는다 --
    짧게 열렸다 닫히는 개방 구간을 놓치지 않기 위함이다."""
    closes = [100.0] + [100.0 + i * 0.2 for i in range(REGIME_BARS_30D)]
    series = build_regime_series(_btc_series(closes))
    assert series[-1][1] == STRONG_BULL  # 이력이 200일에 한참 못 미쳐도 통과


def test_regime_is_none_in_a_flat_market():
    series = build_regime_series(_btc_series([100.0] * (REGIME_BARS_30D + 1)))
    assert series[-1][1] is None


def test_regime_is_none_before_30_days_of_history_exist():
    """레짐을 계산할 수 없는 구간에서 진입하면 게이트가 없는 것과 같다."""
    series = build_regime_series(_btc_series([100.0] * REGIME_BARS_30D))
    assert all(regime is None for _, regime in series)


def test_regime_as_of_returns_none_before_the_series_starts():
    series = [(T0 + timedelta(hours=4), STRONG_BULL)]
    assert regime_as_of(series, T0) is None
    assert regime_as_of(series, T0 + timedelta(hours=5)) == STRONG_BULL


# --- entry_signal (BR19) ---

# 돌파 구간(4봉)보다 거래량 기준선(24봉)이 길므로, 신호가 가능한 첫 인덱스는 24다.
ENTRY_INDEX = max(BREAKOUT_BARS, VOLUME_BASELINE_BARS)


def _entry_setup(volume=300.0, close=11.0, tenkan=2.0, kijun_rising=True, above_cloud=True):
    """평탄한 이력 뒤에 돌파 봉 하나. 각 조건을 개별로 끌 수 있게 만든다."""
    candles = [candle(i, 10.0, high=10.0, volume=100.0) for i in range(ENTRY_INDEX)]
    candles.append(candle(ENTRY_INDEX, close, high=close, volume=volume))
    points = [point(i, 10.0, kijun=1.0) for i in range(ENTRY_INDEX)]
    points.append(
        point(
            ENTRY_INDEX,
            close,
            tenkan=tenkan,
            kijun=1.5 if kijun_rising else 1.0,
            senkou_a=0.5 if above_cloud else close + 1,
            senkou_b=0.4 if above_cloud else close + 2,
        )
    )
    return candles, points


def test_entry_signal_fires_on_a_volume_confirmed_breakout_in_an_uptrend():
    candles, points = _entry_setup()
    assert entry_signal(candles, points, ENTRY_INDEX) is True


def test_entry_signal_requires_the_close_to_clear_the_24h_high():
    candles, points = _entry_setup(close=9.5)
    assert entry_signal(candles, points, ENTRY_INDEX) is False


def test_entry_signal_requires_volume_above_twice_the_average():
    candles, points = _entry_setup(volume=110.0)
    assert entry_signal(candles, points, ENTRY_INDEX) is False


def test_entry_signal_requires_price_above_the_cloud():
    candles, points = _entry_setup(above_cloud=False)
    assert entry_signal(candles, points, ENTRY_INDEX) is False


def test_entry_signal_requires_tenkan_above_kijun():
    candles, points = _entry_setup(tenkan=1.0)
    assert entry_signal(candles, points, ENTRY_INDEX) is False


def test_entry_signal_requires_a_rising_kijun():
    candles, points = _entry_setup(kijun_rising=False)
    assert entry_signal(candles, points, ENTRY_INDEX) is False


def test_entry_signal_is_false_before_enough_history_exists():
    candles, points = _entry_setup()
    assert entry_signal(candles, points, 3) is False


# --- simulate_trade (BR18) ---

def _forward(entry_close: float, bars: list[tuple[float, float, float]]) -> list[Candle]:
    """진입봉 + (high, low, close) 24봉."""
    out = [candle(0, entry_close)]
    out += [candle(i + 1, c, high=h, low=lo) for i, (h, lo, c) in enumerate(bars)]
    return out


FLAT = (100.5, 99.5, 100.0)


def test_simulate_trade_wins_when_the_target_is_touched_first():
    bars = [FLAT] * 5 + [(103.5, 99.5, 103.0)] + [FLAT] * 18
    outcome = simulate_trade(_forward(100.0, bars), 0)
    assert outcome.result == "win"
    assert outcome.ret == TARGET_RETURN


def test_simulate_trade_loses_when_the_stop_is_touched_first():
    bars = [FLAT] * 3 + [(100.5, 97.0, 97.5)] + [(103.5, 99.0, 103.0)] + [FLAT] * 19
    outcome = simulate_trade(_forward(100.0, bars), 0)
    assert outcome.result == "loss"
    assert outcome.ret == -STOP_LOSS


def test_simulate_trade_counts_a_same_bar_tie_as_a_loss():
    """한 봉에서 목표와 손절을 둘 다 만족하면 OHLC로는 선후를 알 수 없다 -- 보수적으로 손절."""
    bars = [(103.5, 97.0, 100.0)] + [FLAT] * 23
    assert simulate_trade(_forward(100.0, bars), 0).result == "loss"


def test_simulate_trade_times_out_and_exits_at_the_last_close():
    bars = [FLAT] * 23 + [(101.0, 99.5, 101.0)]
    outcome = simulate_trade(_forward(100.0, bars), 0)
    assert outcome.result == "timeout"
    assert outcome.ret == 0.01


def test_simulate_trade_returns_none_before_the_window_has_closed():
    bars = [FLAT] * (FORWARD_BARS_1H - 1)
    assert simulate_trade(_forward(100.0, bars), 0) is None


def test_simulate_trade_reports_the_worst_dip_before_exit():
    bars = [(100.5, 99.0, 100.0)] + [(103.5, 99.5, 103.0)] + [FLAT] * 22
    assert simulate_trade(_forward(100.0, bars), 0).drawdown == -0.01


# --- compute_signal_stats (BR21) ---

def _long_history(bars: int = 200) -> tuple[list[Candle], list[IchimokuPoint]]:
    candles = [candle(i, 100.0, high=100.5, low=99.5) for i in range(bars)]
    points = [point(i, 100.0) for i in range(bars)]
    return candles, points


def test_compute_signal_stats_does_not_open_a_new_trade_while_one_is_open():
    """겹치는 진입을 각각 세면 같은 구간의 결과가 여러 번 반영되어 표본이 부풀고 확률이 왜곡된다."""
    candles, points = _long_history()
    regime = [(T0 - timedelta(hours=1), STRONG_BULL)]
    with patch("src.backtest.entry_signal", side_effect=lambda c, p, i: i in (10, 11, 12, 40)):
        stats = compute_signal_stats("TESTUSDT", candles, points, regime)
    assert stats.n == 2  # 10에서 진입하면 34까지 보유하므로 11/12는 무시되고 40이 다음 진입


def test_compute_signal_stats_skips_entries_outside_the_allowed_regime():
    candles, points = _long_history()
    regime = [(T0 - timedelta(hours=1), None)]
    with patch("src.backtest.entry_signal", side_effect=lambda c, p, i: i == 10):
        stats = compute_signal_stats("TESTUSDT", candles, points, regime)
    assert stats.n == 0
    assert stats.hit_rate is None


# --- aggregate_stats ---

def test_aggregate_stats_reports_none_rather_than_zero_without_samples():
    stats = aggregate_stats("TESTUSDT", [])
    assert stats.n == 0 and stats.hit_rate is None and stats.expected_return is None


def test_aggregate_stats_counts_only_wins_as_hits():
    results = [
        TradeOutcome("win", TARGET_RETURN, -0.01),
        TradeOutcome("loss", -STOP_LOSS, -STOP_LOSS),
        TradeOutcome("timeout", 0.005, -0.015),
    ]
    stats = aggregate_stats("TESTUSDT", results)
    assert stats.n == 3 and stats.hit_count == 1
    assert stats.hit_rate == 1 / 3
    assert stats.max_drawdown == -STOP_LOSS


