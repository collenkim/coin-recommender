from datetime import datetime, timezone

from hypothesis import given, settings

from src.data_store import Candle, DataStore, RecommendationRecord
from tests.generators import candle_list_strategy


class FakeRecommendation:
    def __init__(self, market, expected_return, n, hit_count):
        self.market = market
        self.expected_return = expected_return
        self.n = n
        self.hit_count = hit_count


def make_store(tmp_path) -> DataStore:
    return DataStore(str(tmp_path / "test.db"))


def test_upsert_then_get_candles_returns_stored_data(tmp_path):
    store = make_store(tmp_path)
    candle = Candle(
        market="KRW-XRP",
        timeframe="1h",
        candle_time=datetime(2024, 1, 1, tzinfo=timezone.utc),
        open=100.0,
        high=110.0,
        low=90.0,
        close=105.0,
        volume=1000.0,
    )

    upserted = store.upsert_candles("upbit", "KRW-XRP", "1h", [candle])

    assert upserted == 1
    result = store.get_candles("upbit", "KRW-XRP", "1h")
    assert result == [candle]


def test_upsert_updates_existing_candle_on_conflict(tmp_path):
    store = make_store(tmp_path)
    t = datetime(2024, 1, 1, tzinfo=timezone.utc)
    original = Candle("KRW-XRP", "1h", t, 100.0, 110.0, 90.0, 105.0, 1000.0)
    updated = Candle("KRW-XRP", "1h", t, 100.0, 120.0, 90.0, 115.0, 2000.0)

    store.upsert_candles("upbit", "KRW-XRP", "1h", [original])
    store.upsert_candles("upbit", "KRW-XRP", "1h", [updated])

    result = store.get_candles("upbit", "KRW-XRP", "1h")
    assert result == [updated]


def test_upbit_and_binance_tables_are_isolated(tmp_path):
    store = make_store(tmp_path)
    t = datetime(2024, 1, 1, tzinfo=timezone.utc)
    candle = Candle("BTCUSDT", "4h", t, 1.0, 1.0, 1.0, 1.0, 1.0)

    store.upsert_candles("binance", "BTCUSDT", "4h", [candle])

    assert store.get_candles("binance", "BTCUSDT", "4h") == [candle]
    assert store.get_candles("upbit", "BTCUSDT", "4h") == []


def test_get_last_candle_time_returns_none_when_empty(tmp_path):
    store = make_store(tmp_path)
    assert store.get_last_candle_time("upbit", "KRW-XRP", "1h") is None


def test_get_last_candle_time_returns_max(tmp_path):
    store = make_store(tmp_path)
    earlier = Candle("KRW-XRP", "1h", datetime(2024, 1, 1, tzinfo=timezone.utc), 1, 1, 1, 1, 1)
    later = Candle("KRW-XRP", "1h", datetime(2024, 1, 2, tzinfo=timezone.utc), 1, 1, 1, 1, 1)

    store.upsert_candles("upbit", "KRW-XRP", "1h", [earlier, later])

    assert store.get_last_candle_time("upbit", "KRW-XRP", "1h") == later.candle_time


def test_get_candles_since_filters_older_candles(tmp_path):
    store = make_store(tmp_path)
    earlier = Candle("KRW-XRP", "1h", datetime(2024, 1, 1, tzinfo=timezone.utc), 1, 1, 1, 1, 1)
    later = Candle("KRW-XRP", "1h", datetime(2024, 1, 2, tzinfo=timezone.utc), 1, 1, 1, 1, 1)
    store.upsert_candles("upbit", "KRW-XRP", "1h", [earlier, later])

    result = store.get_candles("upbit", "KRW-XRP", "1h", since=datetime(2024, 1, 2, tzinfo=timezone.utc))

    assert result == [later]


# --- Property-based tests (PBT-02: round-trip, idempotence) ---

@settings(deadline=None)
@given(candles=candle_list_strategy(market="KRW-XRP", timeframe="1h"))
def test_pbt_upsert_roundtrip(tmp_path_factory, candles):
    """Round-trip: upserting candles then reading them back returns equal data (PBT-02)."""
    store = DataStore(str(tmp_path_factory.mktemp("db") / "roundtrip.db"))

    store.upsert_candles("upbit", "KRW-XRP", "1h", candles)
    result = store.get_candles("upbit", "KRW-XRP", "1h")

    assert sorted(result, key=lambda c: c.candle_time) == sorted(candles, key=lambda c: c.candle_time)


@settings(deadline=None)
@given(candles=candle_list_strategy(market="KRW-XRP", timeframe="1h"))
def test_pbt_upsert_idempotent(tmp_path_factory, candles):
    """Idempotence: upserting the same candles twice yields the same stored state as once (PBT-04-style, grouped under PBT-02 for this unit)."""
    store = DataStore(str(tmp_path_factory.mktemp("db") / "idempotent.db"))

    store.upsert_candles("upbit", "KRW-XRP", "1h", candles)
    once = store.get_candles("upbit", "KRW-XRP", "1h")
    store.upsert_candles("upbit", "KRW-XRP", "1h", candles)
    twice = store.get_candles("upbit", "KRW-XRP", "1h")

    assert sorted(once, key=lambda c: c.candle_time) == sorted(twice, key=lambda c: c.candle_time)


# --- save_run / get_latest_run / ping (Unit 3) ---

def test_get_latest_run_returns_none_when_never_run(tmp_path):
    store = make_store(tmp_path)
    assert store.get_latest_run() is None


def test_save_run_then_get_latest_run_roundtrip(tmp_path):
    store = make_store(tmp_path)
    run_time = datetime(2024, 1, 1, tzinfo=timezone.utc)
    recs = [FakeRecommendation("KRW-XRP", 0.05, 3, 1), FakeRecommendation("KRW-DOGE", 0.09, 4, 2)]

    store.save_run(run_time, True, recs)
    result = store.get_latest_run()

    assert result.run_time == run_time
    assert result.regime_bullish is True
    assert set(result.recommendations) == {
        RecommendationRecord("KRW-XRP", 0.05, 3, 1),
        RecommendationRecord("KRW-DOGE", 0.09, 4, 2),
    }


def test_save_run_with_zero_recommendations_is_distinguishable_from_never_run(tmp_path):
    store = make_store(tmp_path)
    run_time = datetime(2024, 1, 1, tzinfo=timezone.utc)

    store.save_run(run_time, False, [])
    result = store.get_latest_run()

    assert result is not None
    assert result.recommendations == []
    assert result.regime_bullish is False


def test_get_latest_run_returns_most_recent_run_only(tmp_path):
    store = make_store(tmp_path)
    earlier = datetime(2024, 1, 1, tzinfo=timezone.utc)
    later = datetime(2024, 1, 2, tzinfo=timezone.utc)

    store.save_run(earlier, True, [FakeRecommendation("KRW-OLD", 0.05, 1, 1)])
    store.save_run(later, True, [FakeRecommendation("KRW-NEW", 0.05, 1, 1)])

    result = store.get_latest_run()

    assert result.run_time == later
    assert [r.market for r in result.recommendations] == ["KRW-NEW"]


def test_ping_returns_true_for_healthy_db(tmp_path):
    store = make_store(tmp_path)
    assert store.ping() is True
