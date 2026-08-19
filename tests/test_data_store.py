import sqlite3
from datetime import datetime, timedelta, timezone

from hypothesis import given, settings

from src.data_store import Candle, DataStore, RecommendationRecord, drop_unclosed
from tests.generators import candle_list_strategy


class FakeRecommendation:
    def __init__(self, market, expected_return, n, hit_count, source="upbit"):
        self.market = market
        self.expected_return = expected_return
        self.n = n
        self.hit_count = hit_count
        self.source = source


class FakeOutcome:
    def __init__(self, market, run_time, target_reached, realized_return, evaluated_at):
        self.market = market
        self.run_time = run_time
        self.target_reached = target_reached
        self.realized_return = realized_return
        self.evaluated_at = evaluated_at


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


def test_drop_unclosed_removes_the_still_forming_candle():
    """Both exchanges return the in-progress candle last; using it read a partial bar (BR6)."""
    now = datetime(2026, 8, 10, 7, 1, tzinfo=timezone.utc)
    closed = Candle("KRW-XRP", "1h", datetime(2026, 8, 10, 6, tzinfo=timezone.utc), 1, 1, 1, 1, 1)
    forming = Candle("KRW-XRP", "1h", datetime(2026, 8, 10, 7, tzinfo=timezone.utc), 1, 1, 1, 1, 1)

    assert drop_unclosed([closed, forming], now) == [closed]


def test_drop_unclosed_keeps_a_candle_that_closed_exactly_now():
    now = datetime(2026, 8, 10, 7, tzinfo=timezone.utc)
    just_closed = Candle("KRW-XRP", "1h", datetime(2026, 8, 10, 6, tzinfo=timezone.utc), 1, 1, 1, 1, 1)

    assert drop_unclosed([just_closed], now) == [just_closed]


def test_drop_unclosed_uses_the_candles_own_timeframe():
    now = datetime(2026, 8, 10, 7, 1, tzinfo=timezone.utc)
    # a 4h bar opened at 04:00 closes at 08:00 -- still forming at 07:01
    forming_4h = Candle("BTCUSDT", "4h", datetime(2026, 8, 10, 4, tzinfo=timezone.utc), 1, 1, 1, 1, 1)
    closed_4h = Candle("BTCUSDT", "4h", datetime(2026, 8, 10, 0, tzinfo=timezone.utc), 1, 1, 1, 1, 1)

    assert drop_unclosed([closed_4h, forming_4h], now) == [closed_4h]


def test_get_first_candle_time_returns_none_when_empty(tmp_path):
    store = make_store(tmp_path)
    assert store.get_first_candle_time("binance", "SOLUSDT", "1h") is None


def test_get_first_candle_time_returns_min(tmp_path):
    store = make_store(tmp_path)
    earlier = Candle("SOLUSDT", "1h", datetime(2024, 1, 1, tzinfo=timezone.utc), 1, 1, 1, 1, 1)
    later = Candle("SOLUSDT", "1h", datetime(2024, 1, 2, tzinfo=timezone.utc), 1, 1, 1, 1, 1)

    store.upsert_candles("binance", "SOLUSDT", "1h", [later, earlier])

    assert store.get_first_candle_time("binance", "SOLUSDT", "1h") == earlier.candle_time


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


def test_save_run_persists_source_per_recommendation(tmp_path):
    store = make_store(tmp_path)
    run_time = datetime(2024, 1, 1, tzinfo=timezone.utc)
    recs = [
        FakeRecommendation("KRW-XRP", 0.05, 3, 1, source="upbit"),
        FakeRecommendation("SOLUSDT", 0.09, 4, 2, source="binance"),
    ]

    store.save_run(run_time, True, recs)
    result = store.get_latest_run()

    assert {r.market: r.source for r in result.recommendations} == {"KRW-XRP": "upbit", "SOLUSDT": "binance"}


def test_save_run_roundtrips_entry_guide_fields(tmp_path):
    """BR16: the guide must survive persistence, otherwise GET /recommendations cannot show it."""
    store = make_store(tmp_path)
    run_time = datetime(2024, 1, 1, tzinfo=timezone.utc)
    entry_time = datetime(2024, 1, 1, tzinfo=timezone.utc)
    rec = FakeRecommendation("BANKUSDT", 0.086, 7, 3, source="binance")
    rec.entry_time, rec.entry_price, rec.max_drawdown = entry_time, 100.0, -0.062

    store.save_run(run_time, True, [rec])
    stored = store.get_latest_run().recommendations[0]

    assert stored.entry_time == entry_time
    assert stored.entry_price == 100.0
    assert stored.max_drawdown == -0.062


def test_save_run_accepts_recommendations_without_entry_guide(tmp_path):
    """Duck-typed callers (and legacy objects) that lack the new attributes must still persist."""
    store = make_store(tmp_path)
    run_time = datetime(2024, 1, 1, tzinfo=timezone.utc)

    store.save_run(run_time, True, [FakeRecommendation("KRW-XRP", 0.05, 3, 1)])

    stored = store.get_latest_run().recommendations[0]
    assert stored.entry_time is None and stored.entry_price is None and stored.max_drawdown is None


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


# --- Outcome tracking (BR9/BR11/BR12) ---

def test_migration_adds_outcome_columns_to_pre_existing_db(tmp_path):
    """DBs created before outcome tracking existed (no target_reached/realized_return/evaluated_at
    columns) must open cleanly and gain the new columns (NFR-L3)."""
    db_path = tmp_path / "legacy.db"
    conn = sqlite3.connect(str(db_path))
    conn.execute("CREATE TABLE pipeline_runs (run_time TEXT PRIMARY KEY, regime_bullish INTEGER NOT NULL)")
    conn.execute(
        """
        CREATE TABLE recommendations (
            run_time TEXT NOT NULL, market TEXT NOT NULL, expected_return REAL NOT NULL,
            n INTEGER NOT NULL, hit_count INTEGER NOT NULL, PRIMARY KEY (run_time, market)
        )
        """
    )
    run_time = datetime(2024, 1, 1, tzinfo=timezone.utc)
    conn.execute("INSERT INTO pipeline_runs (run_time, regime_bullish) VALUES (?, ?)", (run_time.isoformat(), 1))
    conn.execute(
        "INSERT INTO recommendations (run_time, market, expected_return, n, hit_count) VALUES (?, ?, ?, ?, ?)",
        (run_time.isoformat(), "KRW-XRP", 0.05, 3, 1),
    )
    conn.commit()
    conn.close()

    store = DataStore(str(db_path))  # must not raise

    result = store.get_latest_run()
    assert result.recommendations == [RecommendationRecord("KRW-XRP", 0.05, 3, 1)]  # target_reached etc default None
    assert result.recommendations[0].source == "upbit"  # legacy rows (pre-source column) treated as upbit (NFR-B2)


def test_get_pending_evaluations_finds_unevaluated_past_recommendation(tmp_path):
    store = make_store(tmp_path)
    run_time = datetime(2024, 1, 1, tzinfo=timezone.utc)
    store.save_run(run_time, True, [FakeRecommendation("KRW-XRP", 0.05, 3, 1)])

    pending = store.get_pending_evaluations(older_than=run_time)

    assert pending == [("KRW-XRP", run_time, "upbit")]


def test_get_pending_evaluations_excludes_runs_after_cutoff(tmp_path):
    store = make_store(tmp_path)
    run_time = datetime(2024, 1, 2, tzinfo=timezone.utc)
    store.save_run(run_time, True, [FakeRecommendation("KRW-XRP", 0.05, 3, 1)])

    pending = store.get_pending_evaluations(older_than=datetime(2024, 1, 1, tzinfo=timezone.utc))

    assert pending == []


def test_get_pending_evaluations_includes_source(tmp_path):
    store = make_store(tmp_path)
    run_time = datetime(2024, 1, 1, tzinfo=timezone.utc)
    store.save_run(run_time, True, [FakeRecommendation("SOLUSDT", 0.05, 3, 1, source="binance")])

    pending = store.get_pending_evaluations(older_than=run_time)

    assert pending == [("SOLUSDT", run_time, "binance")]


def test_get_recent_runs_returns_newest_first(tmp_path):
    store = make_store(tmp_path)
    earlier = datetime(2024, 1, 1, tzinfo=timezone.utc)
    later = datetime(2024, 1, 2, tzinfo=timezone.utc)
    store.save_run(earlier, True, [FakeRecommendation("KRW-OLD", 0.05, 1, 1)])
    store.save_run(later, True, [FakeRecommendation("KRW-NEW", 0.05, 1, 1)])

    runs = store.get_recent_runs(limit=2)

    assert [r.run_time for r in runs] == [later, earlier]
    assert [r.recommendations[0].market for r in runs] == ["KRW-NEW", "KRW-OLD"]


def test_get_recent_runs_respects_limit(tmp_path):
    store = make_store(tmp_path)
    for i in range(5):
        store.save_run(datetime(2024, 1, i + 1, tzinfo=timezone.utc), True, [])

    assert len(store.get_recent_runs(limit=2)) == 2


def test_close_time_supports_the_1m_timeframe_used_by_price_monitoring():
    """BR22 회귀 방지: 1m이 빠져 있으면 drop_unclosed가 KeyError를 내고, 감시 루프의 예외
    처리에 먹혀 '이벤트 0건'으로 조용히 넘어간다 (실제로 그렇게 한 번 놓쳤다)."""
    from src.data_store import TIMEFRAME_HOURS, close_time, drop_unclosed

    assert "1m" in TIMEFRAME_HOURS
    opened = datetime(2026, 8, 11, 6, 0, tzinfo=timezone.utc)
    candle = Candle(
        market="SOLUSDT", timeframe="1m", candle_time=opened,
        open=1.0, high=1.0, low=1.0, close=1.0, volume=1.0,
    )
    assert close_time(candle) == opened + timedelta(minutes=1)
    # 아직 진행 중인 1분봉은 제외, 마감된 봉은 유지
    assert drop_unclosed([candle], now=opened + timedelta(seconds=30)) == []
    assert drop_unclosed([candle], now=opened + timedelta(minutes=1)) == [candle]
