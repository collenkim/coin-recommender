from datetime import datetime, timedelta, timezone
from unittest.mock import MagicMock, patch

import pytest

from src.backtest import STRONG_BULL
from src.config import settings
from src.pipeline import AlreadyRunningError, _lock, evaluate_pending_outcomes, run_recommendation_pipeline


class FakeRecommendation:
    def __init__(self, market="SOLUSDT", expected_return=0.01, n=5, hit_count=3, source="binance"):
        self.market = market
        self.expected_return = expected_return
        self.n = n
        self.hit_count = hit_count
        self.source = source


def _patched_pipeline(**overrides):
    defaults = dict(
        binance_selector_markets=["SOLUSDT"],
        regime=STRONG_BULL,
        recommendations=[FakeRecommendation()],
    )
    defaults.update(overrides)

    mock_store = MagicMock()
    mock_store.get_first_candle_time.return_value = None
    mock_binance_selector_instance = MagicMock()
    mock_binance_selector_instance.get_candidate_markets.return_value = defaults["binance_selector_markets"]

    patches = [
        patch("src.pipeline.BinanceClient"),
        patch("src.pipeline.check_market_regime", return_value=defaults["regime"]),
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
    with patches[0], patches[1], patches[2] as mock_gen, patches[3] as mock_notify, patches[4]:
        result = run_recommendation_pipeline(data_store=mock_store)

    assert result.regime == STRONG_BULL
    assert result.recommendations == mock_gen.return_value
    mock_store.save_run.assert_called_once()
    assert mock_store.save_run.call_args.args[1] is True  # regime is not None
    mock_notify.assert_called_once()


def test_run_outside_an_allowed_regime_is_saved_as_not_bullish():
    patches, mock_store = _patched_pipeline(regime=None, recommendations=[])
    with patches[0], patches[1], patches[2], patches[3], patches[4]:
        result = run_recommendation_pipeline(data_store=mock_store)

    assert result.regime is None
    assert mock_store.save_run.call_args.args[1] is False


def test_only_binance_candles_are_collected():
    """업비트 추천을 뺀 뒤로 업비트 캔들을 모을 이유가 없다 -- 수집이 남아 있으면 순수 낭비다."""
    patches, mock_store = _patched_pipeline()
    with patches[0], patches[1], patches[2], patches[3], patches[4]:
        run_recommendation_pipeline(data_store=mock_store)

    sources = {call.args[0] for call in mock_store.upsert_candles.call_args_list}
    assert sources == {"binance"}


def test_notification_failure_does_not_fail_the_run():
    patches, mock_store = _patched_pipeline()
    with patches[0], patches[1], patches[2], patches[4], patch(
        "src.pipeline.send_notification", side_effect=RuntimeError("webhook down")
    ):
        result = run_recommendation_pipeline(data_store=mock_store)

    assert result is not None
    mock_store.save_run.assert_called_once()  # result already saved before notification attempt


def test_lock_released_after_run_so_next_call_succeeds():
    patches, mock_store = _patched_pipeline()
    with patches[0], patches[1], patches[2], patches[3], patches[4]:
        run_recommendation_pipeline(data_store=mock_store)
        run_recommendation_pipeline(data_store=mock_store)  # would raise AlreadyRunningError if lock leaked


def test_lock_released_even_if_generate_recommendations_raises():
    patches, mock_store = _patched_pipeline()
    with patches[0], patches[1], patches[4], patch(
        "src.pipeline.generate_recommendations", side_effect=RuntimeError("boom")
    ):
        with pytest.raises(RuntimeError):
            run_recommendation_pipeline(data_store=mock_store)

    assert not _lock.locked()


def test_recommendations_are_capped():
    many = [FakeRecommendation(market=f"SYM{i}USDT") for i in range(7)]
    patches, mock_store = _patched_pipeline(recommendations=many)

    with patches[0], patches[1], patches[2], patches[3], patches[4]:
        result = run_recommendation_pipeline(data_store=mock_store)

    expected = settings.recommendations_per_exchange
    assert [r.market for r in result.recommendations] == [f"SYM{i}USDT" for i in range(expected)]


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
