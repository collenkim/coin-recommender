from datetime import datetime, timezone
from unittest.mock import MagicMock, patch

import pytest

from src.pipeline import AlreadyRunningError, _lock, evaluate_pending_outcomes, run_recommendation_pipeline


class FakeRecommendation:
    def __init__(self, market="KRW-XRP", expected_return=0.05, n=3, hit_count=1):
        self.market = market
        self.expected_return = expected_return
        self.n = n
        self.hit_count = hit_count


def _patched_pipeline(**overrides):
    defaults = dict(
        market_selector_markets=["KRW-XRP"],
        regime_bullish=True,
        recommendations=[FakeRecommendation()],
    )
    defaults.update(overrides)

    mock_store = MagicMock()
    mock_selector_instance = MagicMock()
    mock_selector_instance.get_candidate_markets.return_value = defaults["market_selector_markets"]

    patches = [
        patch("src.pipeline.MarketSelector", return_value=mock_selector_instance),
        patch("src.pipeline.UpbitClient"),
        patch("src.pipeline.BinanceClient"),
        patch("src.pipeline.check_market_regime", return_value=defaults["regime_bullish"]),
        patch("src.pipeline.generate_recommendations", return_value=defaults["recommendations"]),
        patch("src.pipeline.send_notification"),
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
    with patches[0], patches[1], patches[2], patches[3], patches[4] as mock_gen, patches[5] as mock_notify:
        result = run_recommendation_pipeline(data_store=mock_store)

    assert result.regime_bullish is True
    assert result.recommendations == mock_gen.return_value
    mock_store.save_run.assert_called_once()
    saved_args = mock_store.save_run.call_args.args
    assert saved_args[1] is True  # regime_bullish
    assert saved_args[2] == mock_gen.return_value
    mock_notify.assert_called_once()


def test_notification_failure_does_not_fail_the_run():
    patches, mock_store = _patched_pipeline()
    with patches[0], patches[1], patches[2], patches[3], patches[4], \
         patch("src.pipeline.send_notification", side_effect=RuntimeError("webhook down")):
        result = run_recommendation_pipeline(data_store=mock_store)

    assert result is not None
    mock_store.save_run.assert_called_once()  # result already saved before notification attempt


def test_lock_released_after_run_so_next_call_succeeds():
    patches, mock_store = _patched_pipeline()
    with patches[0], patches[1], patches[2], patches[3], patches[4], patches[5]:
        run_recommendation_pipeline(data_store=mock_store)
        run_recommendation_pipeline(data_store=mock_store)  # would raise AlreadyRunningError if lock leaked


def test_lock_released_even_if_generate_recommendations_raises():
    patches, mock_store = _patched_pipeline()
    with patches[0], patches[1], patches[2], patches[3], \
         patch("src.pipeline.generate_recommendations", side_effect=RuntimeError("boom")):
        with pytest.raises(RuntimeError):
            run_recommendation_pipeline(data_store=mock_store)

    assert not _lock.locked()


def test_data_collection_failure_for_one_market_does_not_abort_pipeline():
    mock_store = MagicMock()
    mock_store.get_last_candle_time.return_value = None
    mock_upbit = MagicMock()
    mock_upbit.get_ohlcv.side_effect = RuntimeError("network error")

    from src.pipeline import _collect_and_store

    # Should not raise -- failure is caught and logged (Unit 1 graceful degradation, BR7)
    _collect_and_store(mock_store, mock_upbit, "KRW-XRP")

    mock_store.upsert_candles.assert_not_called()


# --- evaluate_pending_outcomes (BR9) ---

def test_evaluate_pending_outcomes_records_outcome_for_each_pending():
    run_time = datetime(2024, 1, 1, tzinfo=timezone.utc)
    now = datetime(2024, 1, 3, tzinfo=timezone.utc)
    mock_store = MagicMock()
    mock_store.get_pending_evaluations.return_value = [("KRW-XRP", run_time)]
    fake_outcome = MagicMock()

    with patch("src.pipeline.evaluate_outcome", return_value=fake_outcome) as mock_evaluate:
        evaluate_pending_outcomes(mock_store, now)

    mock_evaluate.assert_called_once_with("KRW-XRP", run_time, mock_store.get_candles.return_value, now)
    mock_store.record_outcome.assert_called_once_with(fake_outcome)


def test_evaluate_pending_outcomes_skips_when_not_yet_judgeable():
    run_time = datetime(2024, 1, 1, tzinfo=timezone.utc)
    now = datetime(2024, 1, 3, tzinfo=timezone.utc)
    mock_store = MagicMock()
    mock_store.get_pending_evaluations.return_value = [("KRW-XRP", run_time)]

    with patch("src.pipeline.evaluate_outcome", return_value=None):
        evaluate_pending_outcomes(mock_store, now)

    mock_store.record_outcome.assert_not_called()


def test_evaluate_pending_outcomes_isolates_per_item_failure():
    now = datetime(2024, 1, 3, tzinfo=timezone.utc)
    mock_store = MagicMock()
    mock_store.get_pending_evaluations.return_value = [
        ("KRW-BROKEN", datetime(2024, 1, 1, tzinfo=timezone.utc)),
        ("KRW-OK", datetime(2024, 1, 1, tzinfo=timezone.utc)),
    ]
    fake_outcome = MagicMock()

    with patch("src.pipeline.evaluate_outcome", side_effect=[RuntimeError("bad data"), fake_outcome]):
        evaluate_pending_outcomes(mock_store, now)  # should not raise

    mock_store.record_outcome.assert_called_once_with(fake_outcome)
