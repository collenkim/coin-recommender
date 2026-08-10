from datetime import datetime, timedelta, timezone
from unittest.mock import MagicMock, patch

import pytest

from src.pipeline import AlreadyRunningError, _lock, evaluate_pending_outcomes, run_recommendation_pipeline


class FakeRecommendation:
    def __init__(self, market="KRW-XRP", expected_return=0.05, n=3, hit_count=1, source="upbit"):
        self.market = market
        self.expected_return = expected_return
        self.n = n
        self.hit_count = hit_count
        self.source = source


def _patched_pipeline(**overrides):
    defaults = dict(
        market_selector_markets=["KRW-XRP"],
        binance_selector_markets=[],
        regime_bullish=True,
        recommendations=[FakeRecommendation()],
    )
    defaults.update(overrides)

    mock_store = MagicMock()
    mock_selector_instance = MagicMock()
    mock_selector_instance.get_candidate_markets.return_value = defaults["market_selector_markets"]
    mock_binance_selector_instance = MagicMock()
    mock_binance_selector_instance.get_candidate_markets.return_value = defaults["binance_selector_markets"]

    patches = [
        patch("src.pipeline.MarketSelector", return_value=mock_selector_instance),
        patch("src.pipeline.UpbitClient"),
        patch("src.pipeline.BinanceClient"),
        patch("src.pipeline.check_market_regime", return_value=defaults["regime_bullish"]),
        patch("src.pipeline.generate_recommendations", return_value=defaults["recommendations"]),
        patch("src.pipeline.send_notification"),
        patch("src.pipeline.BinanceMarketSelector", return_value=mock_binance_selector_instance),
    ]
    return patches, mock_store


def test_lock_prevents_concurrent_runs():
    _lock.acquire()
    try:
        with pytest.raises(AlreadyRunningError):
            run_recommendation_pipeline(data_store=MagicMock())
    finally:
        _lock.release()


def test_successful_run_saves_result_and_notifies():
    patches, mock_store = _patched_pipeline()
    with patches[0], patches[1], patches[2], patches[3], patches[4] as mock_gen, patches[5] as mock_notify, patches[6]:
        result = run_recommendation_pipeline(data_store=mock_store)

    assert result.regime_bullish is True
    assert result.recommendations == mock_gen.return_value + mock_gen.return_value
    mock_store.save_run.assert_called_once()
    saved_args = mock_store.save_run.call_args.args
    assert saved_args[1] is True  # regime_bullish
    mock_notify.assert_called_once()


def test_notification_failure_does_not_fail_the_run():
    patches, mock_store = _patched_pipeline()
    with patches[0], patches[1], patches[2], patches[3], patches[4], patches[6], \
         patch("src.pipeline.send_notification", side_effect=RuntimeError("webhook down")):
        result = run_recommendation_pipeline(data_store=mock_store)

    assert result is not None
    mock_store.save_run.assert_called_once()  # result already saved before notification attempt


def test_lock_released_after_run_so_next_call_succeeds():
    patches, mock_store = _patched_pipeline()
    with patches[0], patches[1], patches[2], patches[3], patches[4], patches[5], patches[6]:
        run_recommendation_pipeline(data_store=mock_store)
        run_recommendation_pipeline(data_store=mock_store)  # would raise AlreadyRunningError if lock leaked


def test_lock_released_even_if_generate_recommendations_raises():
    patches, mock_store = _patched_pipeline()
    with patches[0], patches[1], patches[2], patches[3], patches[6], \
         patch("src.pipeline.generate_recommendations", side_effect=RuntimeError("boom")):
        with pytest.raises(RuntimeError):
            run_recommendation_pipeline(data_store=mock_store)

    assert not _lock.locked()


def test_recommendations_capped_per_exchange():
    upbit_recs = [FakeRecommendation(market=f"KRW-{i}", source="upbit") for i in range(7)]
    binance_recs = [FakeRecommendation(market=f"SYM{i}USDT", source="binance") for i in range(7)]
    patches, mock_store = _patched_pipeline(recommendations=None)

    with patches[0], patches[1], patches[2], patches[3], patches[6], \
         patch("src.pipeline.generate_recommendations", side_effect=[upbit_recs, binance_recs]), \
         patch("src.pipeline.send_notification"):
        result = run_recommendation_pipeline(data_store=mock_store)

    assert [r.market for r in result.recommendations] == [f"KRW-{i}" for i in range(5)] + [f"SYM{i}USDT" for i in range(5)]


def test_data_collection_failure_for_one_market_does_not_abort_pipeline():
    mock_store = MagicMock()
    mock_store.get_last_candle_time.return_value = None
    mock_upbit = MagicMock()
    mock_upbit.get_ohlcv.side_effect = RuntimeError("network error")

    from src.pipeline import _collect_and_store

    # Should not raise -- failure is caught and logged (Unit 1 graceful degradation, BR7)
    _collect_and_store(mock_store, mock_upbit, "KRW-XRP")

    mock_store.upsert_candles.assert_not_called()


def test_binance_candidate_collection_failure_for_one_timeframe_does_not_abort_pipeline():
    mock_store = MagicMock()
    mock_store.get_first_candle_time.return_value = None
    mock_binance = MagicMock()
    mock_binance.get_klines_since.side_effect = RuntimeError("network error")

    from src.pipeline import _collect_and_store_binance

    # Should not raise -- mirrors _collect_and_store's per-market failure isolation (BR9)
    _collect_and_store_binance(mock_store, mock_binance, "SOLUSDT", timeframes=("1h", "4h"))

    mock_store.upsert_candles.assert_not_called()


def test_binance_candidate_collection_stores_both_timeframes():
    mock_store = MagicMock()
    mock_store.get_first_candle_time.return_value = None
    mock_binance = MagicMock()

    from src.pipeline import _collect_and_store_binance

    _collect_and_store_binance(mock_store, mock_binance, "SOLUSDT", timeframes=("1h", "4h"))

    stored_timeframes = {call.args[2] for call in mock_store.upsert_candles.call_args_list}
    assert stored_timeframes == {"1h", "4h"}


def test_binance_collection_backfills_when_stored_history_is_shallower_than_lookback():
    """The bug this fixes: markets stored under the old 1000-candle cap must reach back, and the
    incremental path only ever moves forward."""
    mock_store = MagicMock()
    mock_store.get_first_candle_time.return_value = datetime.now(timezone.utc) - timedelta(days=10)
    mock_binance = MagicMock()

    from src.pipeline import _collect_and_store_binance

    _collect_and_store_binance(mock_store, mock_binance, "SOLUSDT", timeframes=("1h",))

    mock_binance.get_klines_since.assert_called_once()
    mock_binance.get_klines.assert_not_called()


def test_binance_collection_uses_incremental_once_history_is_deep_enough():
    mock_store = MagicMock()
    mock_store.get_first_candle_time.return_value = datetime.now(timezone.utc) - timedelta(days=999)
    mock_store.get_last_candle_time.return_value = datetime.now(timezone.utc) - timedelta(hours=2)
    mock_binance = MagicMock()
    mock_binance.get_klines.return_value = []

    from src.pipeline import _collect_and_store_binance

    _collect_and_store_binance(mock_store, mock_binance, "SOLUSDT", timeframes=("1h",))

    mock_binance.get_klines_since.assert_not_called()
    mock_binance.get_klines.assert_called_once()


# --- evaluate_pending_outcomes (BR9) ---

def test_evaluate_pending_outcomes_records_outcome_for_each_pending():
    run_time = datetime(2024, 1, 1, tzinfo=timezone.utc)
    now = datetime(2024, 1, 3, tzinfo=timezone.utc)
    mock_store = MagicMock()
    mock_store.get_pending_evaluations.return_value = [("KRW-XRP", run_time, "upbit")]
    fake_outcome = MagicMock()

    with patch("src.pipeline.evaluate_outcome", return_value=fake_outcome) as mock_evaluate:
        evaluate_pending_outcomes(mock_store, now)

    mock_store.get_candles.assert_called_once_with("upbit", "KRW-XRP", "1h")
    mock_evaluate.assert_called_once_with("KRW-XRP", run_time, mock_store.get_candles.return_value, now)
    mock_store.record_outcome.assert_called_once_with(fake_outcome)


def test_evaluate_pending_outcomes_uses_the_correct_source_per_item():
    run_time = datetime(2024, 1, 1, tzinfo=timezone.utc)
    now = datetime(2024, 1, 3, tzinfo=timezone.utc)
    mock_store = MagicMock()
    mock_store.get_pending_evaluations.return_value = [("SOLUSDT", run_time, "binance")]

    with patch("src.pipeline.evaluate_outcome", return_value=None):
        evaluate_pending_outcomes(mock_store, now)

    mock_store.get_candles.assert_called_once_with("binance", "SOLUSDT", "1h")


def test_evaluate_pending_outcomes_skips_when_not_yet_judgeable():
    run_time = datetime(2024, 1, 1, tzinfo=timezone.utc)
    now = datetime(2024, 1, 3, tzinfo=timezone.utc)
    mock_store = MagicMock()
    mock_store.get_pending_evaluations.return_value = [("KRW-XRP", run_time, "upbit")]

    with patch("src.pipeline.evaluate_outcome", return_value=None):
        evaluate_pending_outcomes(mock_store, now)

    mock_store.record_outcome.assert_not_called()


def test_evaluate_pending_outcomes_isolates_per_item_failure():
    now = datetime(2024, 1, 3, tzinfo=timezone.utc)
    mock_store = MagicMock()
    mock_store.get_pending_evaluations.return_value = [
        ("KRW-BROKEN", datetime(2024, 1, 1, tzinfo=timezone.utc), "upbit"),
        ("KRW-OK", datetime(2024, 1, 1, tzinfo=timezone.utc), "upbit"),
    ]
    fake_outcome = MagicMock()

    with patch("src.pipeline.evaluate_outcome", side_effect=[RuntimeError("bad data"), fake_outcome]):
        evaluate_pending_outcomes(mock_store, now)  # should not raise

    mock_store.record_outcome.assert_called_once_with(fake_outcome)
