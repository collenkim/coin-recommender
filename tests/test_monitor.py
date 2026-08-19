from datetime import datetime, timedelta, timezone
from unittest.mock import MagicMock

from src.backtest import STOP_LOSS, TARGET_RETURN
from src.data_store import ENTRY_TOUCHED, STOP_HIT, TARGET_HIT, Candle, DataStore, MonitoredRecommendation
from src.monitor import _events_for, check_price_events

UTC = timezone.utc
ENTRY_TIME = datetime(2026, 8, 11, 6, tzinfo=UTC)
ENTRY_PRICE = 100.0
TARGET_PRICE = ENTRY_PRICE * (1 + TARGET_RETURN)  # 103.0
STOP_PRICE = ENTRY_PRICE * (1 - STOP_LOSS)  # 98.0


def minute(offset: int, high: float, low: float) -> Candle:
    return Candle(
        market="SOLUSDT",
        timeframe="1m",
        candle_time=ENTRY_TIME + timedelta(minutes=offset),
        open=(high + low) / 2,
        high=high,
        low=low,
        close=(high + low) / 2,
        volume=1.0,
    )


def rec(entry_touched_at=None) -> MonitoredRecommendation:
    return MonitoredRecommendation(
        run_time=ENTRY_TIME,
        market="SOLUSDT",
        entry_price=ENTRY_PRICE,
        entry_time=ENTRY_TIME,
        entry_touched_at=entry_touched_at,
    )


# --- _events_for (BR22) ---

def test_no_events_while_price_stays_between_stop_and_target():
    candles = [minute(i, 102.0, 100.5) for i in range(1, 6)]
    assert _events_for(rec(entry_touched_at=ENTRY_TIME), candles) == []


def test_entry_touch_is_reported_when_price_comes_back_down_to_the_entry():
    candles = [minute(1, 102.0, 101.0), minute(2, 101.0, 99.5)]
    events = _events_for(rec(), candles)
    assert [e.kind for e in events] == [ENTRY_TOUCHED]
    assert events[0].price == ENTRY_PRICE
    assert events[0].at == ENTRY_TIME + timedelta(minutes=2)


def test_entry_touch_is_not_reported_again_once_already_recorded():
    candles = [minute(1, 101.0, 99.0)]
    assert _events_for(rec(entry_touched_at=ENTRY_TIME), candles) == []


def test_target_hit_is_reported_and_stops_the_scan():
    candles = [minute(1, 102.0, 101.0), minute(2, 103.5, 102.0), minute(3, 90.0, 90.0)]
    events = _events_for(rec(entry_touched_at=ENTRY_TIME), candles)
    assert [e.kind for e in events] == [TARGET_HIT]  # 목표 도달로 포지션이 끝나 이후 봉은 보지 않는다
    assert events[0].price == TARGET_PRICE


def test_stop_hit_is_reported_and_stops_the_scan():
    candles = [minute(1, 101.0, 97.5), minute(2, 110.0, 109.0)]
    events = _events_for(rec(entry_touched_at=ENTRY_TIME), candles)
    assert [e.kind for e in events] == [STOP_HIT]
    assert events[0].price == STOP_PRICE


def test_same_candle_hitting_both_counts_as_the_stop():
    """simulate_trade와 같은 보수 판정 -- OHLC로는 선후를 알 수 없다."""
    candles = [minute(1, 103.5, 97.0)]
    assert [e.kind for e in _events_for(rec(entry_touched_at=ENTRY_TIME), candles)] == [STOP_HIT]


def test_candles_before_the_entry_bar_are_ignored():
    stale = Candle(
        market="SOLUSDT", timeframe="1m", candle_time=ENTRY_TIME - timedelta(minutes=5),
        open=90.0, high=90.0, low=90.0, close=90.0, volume=1.0,
    )
    assert _events_for(rec(entry_touched_at=ENTRY_TIME), [stale]) == []


def test_entry_touch_and_target_can_both_fire_in_one_pass():
    candles = [minute(1, 101.0, 99.5), minute(2, 103.5, 102.0)]
    assert [e.kind for e in _events_for(rec(), candles)] == [ENTRY_TOUCHED, TARGET_HIT]


# --- check_price_events (BR22) ---

def test_events_are_persisted_so_they_are_not_reported_twice(tmp_path):
    store = DataStore(str(tmp_path / "m.db"))

    class R:
        market, expected_return, n, hit_count = "SOLUSDT", 0.01, 5, 3
        source, entry_price, entry_time, max_drawdown = "binance", ENTRY_PRICE, ENTRY_TIME, -0.01

    store.save_run(ENTRY_TIME, True, [R()])
    client = MagicMock()
    client.get_klines_since.return_value = [minute(1, 103.5, 102.0)]

    now = ENTRY_TIME + timedelta(minutes=10)
    first = check_price_events(store, client, now)
    assert [e.kind for e in first] == [TARGET_HIT]

    second = check_price_events(store, client, now)
    assert second == []  # 목표 도달이 기록돼 감시 대상에서 빠진다


def test_one_market_failing_does_not_block_the_others(tmp_path):
    store = DataStore(str(tmp_path / "m.db"))

    class R:
        def __init__(self, market):
            self.market, self.expected_return, self.n, self.hit_count = market, 0.01, 5, 3
            self.source, self.entry_price, self.entry_time, self.max_drawdown = "binance", ENTRY_PRICE, ENTRY_TIME, -0.01

    store.save_run(ENTRY_TIME, True, [R("AAAUSDT"), R("SOLUSDT")])
    client = MagicMock()
    client.get_klines_since.side_effect = [RuntimeError("network"), [minute(1, 103.5, 102.0)]]

    events = check_price_events(store, client, ENTRY_TIME + timedelta(minutes=10))

    assert [(e.market, e.kind) for e in events] == [("SOLUSDT", TARGET_HIT)]


def test_recommendations_older_than_the_hold_window_are_not_monitored(tmp_path):
    store = DataStore(str(tmp_path / "m.db"))

    class R:
        market, expected_return, n, hit_count = "SOLUSDT", 0.01, 5, 3
        source, entry_price, entry_time, max_drawdown = "binance", ENTRY_PRICE, ENTRY_TIME, -0.01

    store.save_run(ENTRY_TIME, True, [R()])
    client = MagicMock()

    events = check_price_events(store, client, ENTRY_TIME + timedelta(hours=25))

    assert events == []
    client.get_klines_since.assert_not_called()


def test_legacy_rows_without_entry_price_are_skipped(tmp_path):
    store = DataStore(str(tmp_path / "m.db"))

    class Legacy:
        market, expected_return, n, hit_count = "OLDUSDT", 0.01, 5, 3

    store.save_run(ENTRY_TIME, True, [Legacy()])
    client = MagicMock()

    assert check_price_events(store, client, ENTRY_TIME + timedelta(minutes=10)) == []
    client.get_klines_since.assert_not_called()


def test_marking_one_track_does_not_silence_the_others(tmp_path):
    """BR36: 같은 종목이 단타(+2%)·장기(+10%)에 동시에 뽑힐 수 있다. track 없이 기록하면
    단타 도달이 장기까지 '알림 완료'로 표시해 장기 도달을 영영 못 알린다."""
    from src.data_store import TARGET_HIT, DataStore

    store = DataStore(str(tmp_path / "t.db"))
    run_time = datetime(2026, 8, 20, tzinfo=timezone.utc)

    class Rec:
        def __init__(self, track):
            self.market = "SOLUSDT"
            self.expected_return = 0.01
            self.n = 100
            self.hit_count = 30
            self.source = "binance"
            self.entry_time = run_time
            self.entry_price = 77.0
            self.max_drawdown = -0.01
            self.track = track

    store.save_run(run_time, True, [Rec("day"), Rec("long")])
    store.mark_price_event(run_time, "SOLUSDT", TARGET_HIT, run_time, "day")

    still_watched = {r.track for r in store.get_monitorable_recommendations(run_time - timedelta(hours=1))}
    assert "long" in still_watched  # 장기는 계속 감시 대상
    assert "day" not in still_watched  # 단타만 종료


def test_scheduler_checks_price_every_two_minutes():
    from fastapi import FastAPI

    from src.scheduler import _MONITOR_JOB_ID, start_scheduler, stop_scheduler

    app = FastAPI()
    scheduler = start_scheduler(app)
    try:
        job = scheduler.get_job(_MONITOR_JOB_ID)
        minute = next(f for f in job.trigger.fields if f.name == "minute")
        assert str(minute) == "*/2"
    finally:
        stop_scheduler(app)
