from datetime import datetime, timedelta, timezone

import pytest

from src.data_store import Candle
from src.features import compute_ichimoku
from src.long_track import (
    LONG_HOLD_BARS_4H,
    LONG_MIN_SAMPLES,
    LONG_STOP_LOSS,
    LONG_TARGET_RETURN,
    LONG_VOLUME_MULTIPLE,
    LONG_VOLUME_WINDOW_BARS,
    OPEN_CYCLE_YEARS,
    compute_long_stats,
    cycle_position,
    long_entry_signal,
    next_open_at,
    simulate_long_trade,
    volume_ratio,
)

UTC = timezone.utc
_HALVING_2024 = datetime(2024, 4, 20, tzinfo=UTC)


def _candles(prices, volumes=None, start=datetime(2024, 5, 1, tzinfo=UTC), market="SOLUSDT"):
    volumes = volumes or [1.0] * len(prices)
    return [
        Candle(
            market=market,
            timeframe="4h",
            candle_time=start + timedelta(hours=4 * i),
            open=p,
            high=p,
            low=p,
            close=p,
            volume=v,
        )
        for i, (p, v) in enumerate(zip(prices, volumes))
    ]


# --- 사이클 게이트 ---


def test_cycle_position_reports_year_since_the_most_recent_halving():
    position = cycle_position(_HALVING_2024 + timedelta(days=100))
    assert position is not None
    assert position.halving == _HALVING_2024
    assert position.year == 0
    assert position.is_open


def test_gate_is_closed_in_year_one_to_two():
    """1~2년차는 실측 기대수익이 유일하게 음수(-0.13%)라 닫는다."""
    position = cycle_position(_HALVING_2024 + timedelta(days=400))
    assert position is not None and position.year == 1
    assert not position.is_open


def test_gate_is_open_in_year_two_to_three():
    position = cycle_position(_HALVING_2024 + timedelta(days=800))
    assert position is not None and position.year == 2
    assert position.is_open


def test_gate_is_closed_in_year_three_to_four():
    position = cycle_position(_HALVING_2024 + timedelta(days=1200))
    assert position is not None and position.year == 3
    assert not position.is_open


def test_open_years_are_exactly_the_measured_positive_ones():
    assert set(OPEN_CYCLE_YEARS) == {0, 2}


def test_cycle_position_is_none_before_the_first_halving():
    assert cycle_position(datetime(2010, 1, 1, tzinfo=UTC)) is None


def test_next_open_at_is_none_while_open():
    assert next_open_at(_HALVING_2024 + timedelta(days=10)) is None


def test_next_open_at_points_at_the_next_open_year():
    opens = next_open_at(_HALVING_2024 + timedelta(days=400))  # 1~2년차 -> 2~3년차를 가리켜야 함
    assert opens is not None
    assert (opens - _HALVING_2024).days == pytest.approx(int(2 * 365.25), abs=1)


# --- 거래량비 ---


def test_volume_ratio_is_none_without_a_full_baseline_window():
    assert volume_ratio(_candles([100.0] * 10), 9) is None


def test_volume_ratio_compares_recent_against_the_earlier_baseline():
    volumes = [1.0] * LONG_VOLUME_WINDOW_BARS
    volumes[-42:] = [2.0] * 42  # 최근 7일만 2배
    candles = _candles([100.0] * LONG_VOLUME_WINDOW_BARS, volumes)
    assert volume_ratio(candles, len(candles) - 1) == pytest.approx(2.0)


# --- 진입 조건 ---


def _cloud_ready(price_above_cloud: bool, volume_surge: bool):
    """구름이 계산될 만큼 긴 이력 + 마지막 봉의 조건만 통제한다."""
    n = max(LONG_VOLUME_WINDOW_BARS, 120)
    prices = [100.0] * n
    volumes = [1.0] * n
    if volume_surge:
        volumes[-42:] = [2.0] * 42
    prices = prices + [200.0 if price_above_cloud else 50.0]
    volumes = volumes + [2.0 if volume_surge else 0.1]
    candles = _candles(prices, volumes)
    return candles, compute_ichimoku(candles)


def test_entry_requires_price_above_cloud():
    candles, points = _cloud_ready(price_above_cloud=False, volume_surge=True)
    assert not long_entry_signal(candles, points, len(points) - 1)


def test_entry_requires_volume_surge():
    candles, points = _cloud_ready(price_above_cloud=True, volume_surge=False)
    assert not long_entry_signal(candles, points, len(points) - 1)


def test_entry_fires_when_both_hold():
    candles, points = _cloud_ready(price_above_cloud=True, volume_surge=True)
    assert long_entry_signal(candles, points, len(points) - 1)


def test_entry_is_false_during_ichimoku_warmup():
    candles = _candles([100.0] * 5)
    points = compute_ichimoku(candles)
    assert not long_entry_signal(candles, points, len(points) - 1)


def test_volume_threshold_is_exclusive():
    """1.3배 '초과'다 -- 경계값이 통과하면 측정 조건과 어긋난다."""
    n = LONG_VOLUME_WINDOW_BARS
    volumes = [1.0] * n
    volumes[-42:] = [LONG_VOLUME_MULTIPLE] * 42
    candles = _candles([100.0] * n, volumes)
    assert volume_ratio(candles, len(candles) - 1) == pytest.approx(LONG_VOLUME_MULTIPLE)
    assert not long_entry_signal(candles, compute_ichimoku(candles), len(candles) - 1)


# --- 매매 시뮬레이션 ---


def _padded(prices):
    """판정에 필요한 540봉을 채운다 -- 창이 안 차면 판정 불가(None)로 빠진다."""
    return _candles(prices + [prices[-1]] * (LONG_HOLD_BARS_4H + 1 - len(prices)))


def test_target_hit_is_a_win_at_the_long_target():
    candles = _padded([100.0, 100.0 * (1 + LONG_TARGET_RETURN)])
    outcome, exit_index = simulate_long_trade(candles, 0)
    assert outcome.result == "win"
    assert outcome.ret == pytest.approx(LONG_TARGET_RETURN)
    assert exit_index == 1


def test_stop_hit_is_a_loss_at_the_long_stop():
    candles = _padded([100.0, 100.0 * (1 - LONG_STOP_LOSS)])
    outcome, _ = simulate_long_trade(candles, 0)
    assert outcome.result == "loss"
    assert outcome.ret == pytest.approx(-LONG_STOP_LOSS)


def test_stop_takes_precedence_when_one_bar_spans_both():
    """단기 트랙 `simulate_trade`와 같은 보수적 규칙 -- 한 봉에서 둘 다 닿으면 손절로 본다."""
    candles = _padded([100.0, 100.0])
    spanning = Candle("SOLUSDT", "4h", candles[1].candle_time, 100.0, 130.0, 85.0, 100.0, 1.0)
    outcome, _ = simulate_long_trade([candles[0], spanning] + candles[2:], 0)
    assert outcome.result == "loss"


def test_timeout_settles_at_the_closing_price_after_the_hold_window():
    prices = [100.0] + [105.0] * (LONG_HOLD_BARS_4H + 5)
    outcome, exit_index = simulate_long_trade(_candles(prices), 0)
    assert outcome.result == "timeout"
    assert outcome.ret == pytest.approx(0.05)
    assert exit_index == LONG_HOLD_BARS_4H


def test_simulate_returns_none_without_a_following_bar():
    assert simulate_long_trade(_candles([100.0]), 0) is None


def test_simulate_returns_none_while_the_hold_window_is_still_open():
    """진행 중인 매매를 타임아웃으로 세면 표본이 통째로 왜곡된다 -- 개방 직후 구간은 거의 전부가
    미완료라 실제로 ACE가 표본 1건이어야 할 곳에서 27건으로 부풀었던 결함이다."""
    prices = [100.0] * LONG_HOLD_BARS_4H  # 진입 뒤 539봉만 존재 (540봉 필요)
    assert simulate_long_trade(_candles(prices), 0) is None


# --- 표본 산출 ---


def test_stats_only_count_entries_from_the_same_cycle_year():
    """2~3년차에 0~1년차 성적(42.1%)을 표시하면 과대 표시가 된다 -- 실측 2~3년차는 35.8%."""
    candles, points = _cloud_ready(price_above_cloud=True, volume_surge=True)
    same_year = compute_long_stats("SOLUSDT", candles, points, cycle_position(candles[-1].candle_time).year)
    other_year = compute_long_stats("SOLUSDT", candles, points, 3)
    assert other_year.n == 0
    assert same_year.n >= other_year.n


def test_stats_are_empty_when_nothing_matches():
    candles = _candles([100.0] * 30)
    stats = compute_long_stats("SOLUSDT", candles, compute_ichimoku(candles), 0)
    assert stats.n == 0
    assert stats.hit_rate is None


def test_min_samples_matches_the_short_track_floor():
    assert LONG_MIN_SAMPLES == 10
