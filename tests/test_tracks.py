from datetime import datetime, timedelta, timezone

import pytest

from src.data_store import TIMEFRAME_HOURS, Candle
from src.features import above_cloud, compute_ichimoku
from src.tracks import (
    COLLECTED_TIMEFRAMES,
    LONG,
    MID,
    MIN_HIT_RATE,
    RSI_MIN,
    SHORT,
    TRACK_BY_KEY,
    TRACKS,
    ULTRA,
    EntryContext,
    SimSeries,
    TrackSpec,
    aux_ok,
    bars_for,
    compute_track_stats,
    entry_ok,
    golden_cross,
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


def test_all_tracks_enter_on_4h_and_judge_on_30m():
    """BR27 실측: 네 트랙 모두 진입 4시간봉 / 판정 30분봉이 기대수익 최고였다."""
    for spec in TRACKS:
        assert spec.timeframe == "4h"
        assert spec.sim_timeframe == "30m"


def test_simulation_timeframe_is_finer_than_the_entry_timeframe():
    """같은 봉으로 판정하면 보유가 짧은 트랙일수록 판정 봉수가 적어 손실 쪽으로 편향된다."""
    from src.tracks import TIMEFRAME_HOURS as TFH

    for spec in TRACKS:
        assert TFH[spec.sim_timeframe] < TFH[spec.timeframe]


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


def test_bars_for_converts_hold_hours_to_the_simulation_timeframe():
    assert bars_for(TRACK_BY_KEY[ULTRA]) == 16  # 8시간 / 30분봉
    assert bars_for(TRACK_BY_KEY[MID]) == 48  # 24시간 / 30분봉
    assert bars_for(TRACK_BY_KEY[LONG]) == 336  # 168시간 / 30분봉


# --- 진입 신호 (골든크로스) ---


def test_latest_entry_returns_none_without_a_golden_cross():
    candles = _candles([100.0] * 200)
    assert latest_entry(candles, compute_ichimoku(candles), TRACK_BY_KEY[ULTRA]) is None


# --- 시뮬레이션 ---


# 진입봉(4h) 하나가 30분봉 8개에 대응한다. 판정봉 열은 진입봉 시작 시각부터 만들어야
# `index_at(진입봉 마감)`이 유효한 인덱스를 돌려준다.
_BARS_PER_ENTRY = 8


def _sim_series(overrides=None, extra=8, spec=None, start=datetime(2025, 1, 1, tzinfo=UTC), flat=100.0):
    """30분 판정봉 열. `overrides`는 {진입 후 몇 번째 봉: (고가, 저가)}."""
    overrides = overrides or {}
    total = _BARS_PER_ENTRY + bars_for(spec) + extra
    bars = []
    for i in range(total):
        t = start + timedelta(minutes=30 * i)
        offset = i - _BARS_PER_ENTRY + 1  # 진입봉 마감 다음 봉이 1
        high, low = overrides.get(offset, (flat, flat))
        bars.append(Candle("SOLUSDT", "30m", t, flat, high, low, flat, 1.0))
    return SimSeries.build(bars)


def _sim_after_entry(second_high, second_low, spec):
    return _sim_series({1: (second_high, second_low)}, spec=spec)


def test_target_hit_is_a_win():
    spec = TRACK_BY_KEY[ULTRA]
    result, ret, _ = simulate(_candles([100.0, 100.0]), 0, spec, _sim_after_entry(102.0, 100.0, spec))
    assert result == "win"
    assert ret == pytest.approx(spec.target)


def test_stop_hit_is_a_loss():
    spec = TRACK_BY_KEY[ULTRA]
    result, ret, _ = simulate(_candles([100.0, 100.0]), 0, spec, _sim_after_entry(100.0, 98.0, spec))
    assert result == "loss"
    assert ret == pytest.approx(-spec.stop)


def test_stop_takes_precedence_within_a_single_bar():
    """한 판정봉에서 둘 다 닿으면 선후를 알 수 없으므로 보수적으로 손절로 본다."""
    spec = TRACK_BY_KEY[ULTRA]
    result, _, _ = simulate(_candles([100.0, 100.0]), 0, spec, _sim_after_entry(105.0, 97.0, spec))
    assert result == "loss"


def test_timeout_settles_at_the_closing_price():
    spec = TRACK_BY_KEY[ULTRA]
    result, ret, _ = simulate(_candles([100.0, 100.0]), 0, spec, _sim_series(spec=spec, flat=100.5))
    assert result == "timeout"
    assert ret == pytest.approx(0.005)


def test_simulate_returns_none_while_the_hold_window_is_still_open():
    """진행 중인 매매를 타임아웃으로 세면 표본이 왜곡된다 -- BR24 구현에서 실제로 겪은 결함."""
    spec = TRACK_BY_KEY[ULTRA]
    short = _sim_series(spec=spec, extra=-1)  # 보유 창보다 한 봉 모자람
    assert simulate(_candles([100.0, 100.0]), 0, spec, short) is None


# --- 표본 산출 ---


def _flat_sim(entry_candles, spec):
    """진입봉 전체 구간을 덮는 평탄한 30분 판정봉."""
    start = entry_candles[0].candle_time
    total = len(entry_candles) * _BARS_PER_ENTRY + bars_for(spec) + 4
    return SimSeries.build(
        [
            Candle("SOLUSDT", "30m", start + timedelta(minutes=30 * i), 100.0, 100.0, 100.0, 100.0, 1.0)
            for i in range(total)
        ]
    )


def test_stats_are_empty_when_there_is_no_golden_cross():
    candles = _candles([100.0] * 200)
    spec = TRACK_BY_KEY[ULTRA]
    stats = compute_track_stats(candles, compute_ichimoku(candles), spec, _flat_sim(candles, spec))
    assert stats["n"] == 0
    assert stats["hit_rate"] is None


def test_golden_cross_fires_only_on_the_crossing_bar():
    points = compute_ichimoku(_candles([100.0] * 60 + [130.0] * 30))
    crossings = [i for i in range(1, len(points)) if golden_cross(points, i)]
    assert crossings
    for i in crossings:
        assert points[i].tenkan > points[i].kijun
        assert points[i - 1].tenkan <= points[i - 1].kijun


def test_stats_count_entries_without_overlapping_holds():
    """보유 중 새 진입을 잡으면 같은 구간이 여러 번 반영되어 표본이 부푼다."""
    spec = TRACK_BY_KEY[ULTRA]
    prices = [100.0] * 120
    for _ in range(10):
        prices += [200.0, 100.0]
    prices += [100.0] * 20
    candles = _candles(prices)
    stats = compute_track_stats(candles, compute_ichimoku(candles), spec, _flat_sim(candles, spec))
    assert stats["n"] == stats["hit_count"] + stats["loss_count"] + stats["timeout_count"]


# --- BR26 보조지표 / 문턱 ---

def _ctx(btc=True, rsi_value=60.0, n=200):
    from datetime import datetime as _dt

    base = _dt(2020, 1, 1, tzinfo=UTC)
    return EntryContext(btc_cloud=[(base, btc)], rsi=[rsi_value] * n)


def test_aux_requires_btc_above_cloud():
    candles = _candles([100.0] * 50)
    assert not aux_ok(_ctx(btc=False), candles, 40)


def test_aux_does_not_use_the_daily_cloud():
    """일봉 구름 조건은 룩어헤드로 좋아 보였을 뿐, 마감 기준으로 재면 전 트랙에서 해로웠다
    (초단기 -0.23% / 단기 -0.13%). EntryContext에 남아 있으면 다시 들어가기 쉽다."""
    assert not hasattr(EntryContext, "daily_cloud")
    assert "daily_cloud" not in EntryContext.__dataclass_fields__


def test_aux_requires_rsi_at_or_above_the_floor():
    candles = _candles([100.0] * 50)
    assert not aux_ok(_ctx(rsi_value=RSI_MIN - 0.1), candles, 40)
    assert aux_ok(_ctx(rsi_value=RSI_MIN), candles, 40)


def test_aux_rejects_when_rsi_is_unknown():
    candles = _candles([100.0] * 50)
    context = EntryContext(btc_cloud=_ctx().btc_cloud, rsi=[None] * 200)
    assert not aux_ok(context, candles, 40)


def test_aux_defaults_to_false_before_any_history():
    """조회 시점이 시계열보다 이르면 False -- 모르는 상태로 진입하지 않는다."""
    from datetime import datetime as _dt

    candles = _candles([100.0] * 50)
    late = EntryContext(btc_cloud=[(_dt(2099, 1, 1, tzinfo=UTC), True)], rsi=[60.0] * 200)
    assert not aux_ok(late, candles, 40)


def test_aux_passes_through_when_no_context_given():
    candles = _candles([100.0] * 50)
    assert aux_ok(None, candles, 40)


def test_hit_rate_floor_sits_below_measured_capability():
    """45%는 실측 능력(36.3%)보다 높아 우연히 높게 나온 코인만 통과시켰다."""
    assert 0.25 <= MIN_HIT_RATE <= 0.30


def test_tracks_have_no_per_track_phase_restriction():
    """트랙은 목표·보유 기간의 정의일 뿐이다 -- 게이트가 연 국면에서는 네 트랙이 모두 동작한다."""
    assert not hasattr(TrackSpec, "only_phases")
    assert "only_phases" not in TrackSpec.__dataclass_fields__


def test_stats_apply_the_aux_filter():
    """보조지표가 걸리면 같은 이력에서 표본이 줄어야 한다."""
    # 골든크로스가 실제로 발생하는 형태: 횡보 후 상승 전환을 반복시킨다.
    prices = [100.0] * 60
    for _ in range(4):
        prices += [100.0 + i for i in range(30)] + [130.0 - i for i in range(30)]
    candles = _candles(prices)
    points = compute_ichimoku(candles)
    spec = TRACK_BY_KEY[ULTRA]
    sim = _flat_sim(candles, spec)
    without = compute_track_stats(candles, points, spec, sim)
    blocked = compute_track_stats(candles, points, spec, sim, _ctx(btc=False, n=len(candles)))
    assert blocked["n"] == 0
    assert without["n"] > 0


def test_only_the_long_track_requires_price_above_the_cloud():
    """실측: 장기 +0.56% -> +1.06%로 크게 개선되지만 초단기는 +0.15% -> +0.12%로 손해."""
    assert TRACK_BY_KEY[LONG].require_above_cloud
    for key in (ULTRA, SHORT, MID):
        assert not TRACK_BY_KEY[key].require_above_cloud


def test_entry_ok_adds_the_cloud_condition_only_where_configured():
    points = compute_ichimoku(_candles([100.0] * 60 + [130.0] * 30))
    crossings = [i for i in range(1, len(points)) if golden_cross(points, i)]
    assert crossings
    for i in crossings:
        assert entry_ok(points, i, TRACK_BY_KEY[ULTRA])  # 구름 조건 없음
        assert entry_ok(points, i, TRACK_BY_KEY[LONG]) == above_cloud(points[i])
