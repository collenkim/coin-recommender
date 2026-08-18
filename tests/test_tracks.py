from datetime import datetime, timedelta, timezone

import pytest

from src.data_store import TIMEFRAME_HOURS, Candle
from src.features import compute_ichimoku
from src.tracks import (
    COLLECTED_TIMEFRAMES,
    LONG,
    MID,
    SHORT,
    TRACK_BY_KEY,
    TRACKS,
    ULTRA,
    bars_for,
    cloud_breakout,
    compute_track_stats,
    latest_entry,
    simulate,
)

UTC = timezone.utc


def _candles(prices, timeframe="4h", start=datetime(2025, 1, 1, tzinfo=UTC)):
    step = timedelta(hours=int(4 if timeframe == "4h" else 1))
    return [
        Candle(
            market="SOLUSDT",
            timeframe=timeframe,
            candle_time=start + step * i,
            open=p,
            high=p,
            low=p,
            close=p,
            volume=1.0,
        )
        for i, p in enumerate(prices)
    ]


# --- 트랙 정의 ---


def test_four_tracks_cover_the_requested_horizons():
    assert [t.key for t in TRACKS] == [ULTRA, SHORT, MID, LONG]
    assert [(t.target, t.hold_hours) for t in TRACKS] == [
        (0.02, 8),
        (0.03, 12),
        (0.05, 24),
        (0.10, 168),
    ]


def test_entry_timeframes_match_the_measured_best():
    """실측(5종목·365일): 초단기/단기는 4시간봉이 1위(25.1%/14.6%), 중기는 1시간봉(14.1%)."""
    assert TRACK_BY_KEY[ULTRA].timeframe == "4h"
    assert TRACK_BY_KEY[SHORT].timeframe == "4h"
    assert TRACK_BY_KEY[MID].timeframe == "1h"


def test_collected_timeframes_exclude_the_expensive_short_ones():
    """1m/3m/5m은 20종 9년 기준 23GB인데 초단기 기여가 창마다 부호가 갈렸다."""
    assert "1m" not in COLLECTED_TIMEFRAMES
    assert "3m" not in COLLECTED_TIMEFRAMES
    assert "5m" not in COLLECTED_TIMEFRAMES
    assert set(COLLECTED_TIMEFRAMES) == {"15m", "30m", "1h", "4h", "1d", "1w", "1M"}


def test_every_collected_timeframe_is_registered_for_close_time():
    """등록이 빠지면 drop_unclosed가 KeyError를 내고 수집 루프에 먹혀 조용히 0건이 된다."""
    for timeframe in COLLECTED_TIMEFRAMES:
        assert timeframe in TIMEFRAME_HOURS


def test_bars_for_converts_hold_hours_to_the_entry_timeframe():
    assert bars_for(TRACK_BY_KEY[ULTRA]) == 2  # 8시간 / 4시간봉
    assert bars_for(TRACK_BY_KEY[MID]) == 24  # 24시간 / 1시간봉
    assert bars_for(TRACK_BY_KEY[LONG]) == 42  # 168시간 / 4시간봉


# --- 구름대 돌파 ---


def _cloud_series(final_close):
    """구름이 계산될 만큼 긴 이력 뒤에 마지막 봉만 통제한다."""
    prices = [100.0] * 120 + [final_close]
    candles = _candles(prices)
    return candles, compute_ichimoku(candles)


def test_breakout_fires_when_price_crosses_above_the_cloud():
    candles, points = _cloud_series(200.0)
    assert cloud_breakout(points, len(points) - 1)


def test_breakout_does_not_fire_below_the_cloud():
    candles, points = _cloud_series(50.0)
    assert not cloud_breakout(points, len(points) - 1)


def test_breakout_is_the_crossing_moment_not_the_state():
    """이미 구름 위에 머물러 있는 봉은 돌파가 아니다 -- 진입가가 움직임의 시작에 붙어야 한다."""
    prices = [100.0] * 120 + [200.0, 210.0]
    candles = _candles(prices)
    points = compute_ichimoku(candles)
    assert cloud_breakout(points, len(points) - 2)  # 처음 뚫은 봉
    assert not cloud_breakout(points, len(points) - 1)  # 이미 위에 있는 봉


def test_breakout_is_false_during_warmup():
    candles = _candles([100.0] * 5)
    assert not cloud_breakout(compute_ichimoku(candles), 4)


def test_latest_entry_returns_none_without_a_breakout():
    candles, points = _cloud_series(50.0)
    assert latest_entry(candles, points) is None


# --- 시뮬레이션 ---


def _pad(prices, spec):
    return _candles(prices + [prices[-1]] * (bars_for(spec) + 1 - len(prices)), spec.timeframe)


def test_target_hit_is_a_win():
    spec = TRACK_BY_KEY[ULTRA]
    result, ret, _ = simulate(_pad([100.0, 102.0], spec), 0, spec)
    assert result == "win"
    assert ret == pytest.approx(spec.target)


def test_stop_hit_is_a_loss():
    spec = TRACK_BY_KEY[ULTRA]
    result, ret, _ = simulate(_pad([100.0, 98.0], spec), 0, spec)
    assert result == "loss"
    assert ret == pytest.approx(-spec.stop)


def test_stop_takes_precedence_within_a_single_bar():
    """단기 트랙 simulate_trade와 같은 보수적 규칙."""
    spec = TRACK_BY_KEY[ULTRA]
    candles = _pad([100.0, 100.0], spec)
    spanning = Candle("SOLUSDT", "4h", candles[1].candle_time, 100.0, 105.0, 97.0, 100.0, 1.0)
    result, _, _ = simulate([candles[0], spanning] + candles[2:], 0, spec)
    assert result == "loss"


def test_timeout_settles_at_the_closing_price():
    spec = TRACK_BY_KEY[ULTRA]
    result, ret, _ = simulate(_candles([100.0] + [100.5] * (bars_for(spec) + 2)), 0, spec)
    assert result == "timeout"
    assert ret == pytest.approx(0.005)


def test_simulate_returns_none_while_the_hold_window_is_still_open():
    """진행 중인 매매를 타임아웃으로 세면 표본이 왜곡된다 -- BR24 구현에서 실제로 겪은 결함."""
    spec = TRACK_BY_KEY[LONG]
    assert simulate(_candles([100.0] * bars_for(spec)), 0, spec) is None


# --- 표본 산출 ---


def test_stats_are_empty_when_nothing_breaks_out():
    candles = _candles([100.0] * 200)
    stats = compute_track_stats(candles, compute_ichimoku(candles), TRACK_BY_KEY[ULTRA])
    assert stats["n"] == 0
    assert stats["hit_rate"] is None


def test_stats_count_breakouts_without_overlapping_holds():
    """보유 중 새 진입을 잡으면 같은 구간이 여러 번 반영되어 표본이 부푼다."""
    spec = TRACK_BY_KEY[ULTRA]
    prices = [100.0] * 120
    for _ in range(10):
        prices += [200.0, 100.0]  # 돌파 -> 복귀 반복
    prices += [100.0] * 20
    candles = _candles(prices)
    stats = compute_track_stats(candles, compute_ichimoku(candles), spec)
    assert stats["n"] <= 10  # 돌파 횟수를 넘지 않는다
    assert stats["n"] == stats["hit_count"] + stats["loss_count"] + stats["timeout_count"]
