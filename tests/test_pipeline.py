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
    mock_store.get_last_candle_time.return_value = None  # BR29: 이력 없음 -> 수집 필요
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
    mock_store.get_last_candle_time.return_value = None
    mock_binance = MagicMock()
    mock_binance.get_klines_since.side_effect = RuntimeError("network error")

    from src.pipeline import _collect_and_store_binance

    # Should not raise -- mirrors _collect_and_store's per-market failure isolation (BR9)
    _collect_and_store_binance(mock_store, mock_binance, "SOLUSDT", timeframes=("1h", "4h"))

    mock_store.upsert_candles.assert_not_called()


def test_binance_candidate_collection_stores_both_timeframes():
    mock_store = MagicMock()
    mock_store.get_first_candle_time.return_value = None
    mock_store.get_last_candle_time.return_value = None
    mock_binance = MagicMock()

    from src.pipeline import _collect_and_store_binance

    _collect_and_store_binance(mock_store, mock_binance, "SOLUSDT", timeframes=("1h", "4h"))

    stored_timeframes = {call.args[2] for call in mock_store.upsert_candles.call_args_list}
    assert stored_timeframes == {"1h", "4h"}


def _earliest_probe(candle_time):
    """`_is_exchange_earliest`가 쓰는 1봉 조회의 응답."""
    from src.data_store import Candle

    return [Candle("SOLUSDT", "1h", candle_time, 1.0, 1.0, 1.0, 1.0, 1.0)]


def test_binance_collection_backfills_when_stored_history_is_shallower_than_lookback():
    """The bug this fixes: markets stored under the old 1000-candle cap must reach back, and the
    incremental path only ever moves forward."""
    mock_store = MagicMock()
    mock_store.get_first_candle_time.return_value = datetime.now(timezone.utc) - timedelta(days=10)
    mock_store.get_last_candle_time.return_value = None  # BR29: 최신 봉이 없으니 수집 필요
    mock_store.get_exchange_earliest.return_value = None  # 캐시 미보유 -> 조회
    mock_binance = MagicMock()
    # 거래소는 훨씬 오래된 봉을 갖고 있다 -- 아직 받을 과거가 남았으므로 백필해야 한다.
    mock_binance.get_klines.return_value = _earliest_probe(datetime.now(timezone.utc) - timedelta(days=2000))

    from src.pipeline import _collect_and_store_binance

    _collect_and_store_binance(mock_store, mock_binance, "SOLUSDT", timeframes=("1h",))

    mock_binance.get_klines_since.assert_called_once()


def test_binance_collection_stops_refetching_once_it_holds_the_exchange_earliest_bar():
    """2026-08-18 결함: lookback을 12년으로 늘리자 `first > target_start`가 영원히 참이 되어
    (바이낸스 자체가 2017년 시작) 모든 종목을 매 실행마다 전량 재수집했다 -- 실측 136초/약 600요청.
    거래소의 첫 봉을 이미 갖고 있으면 더 받을 과거가 없으므로 증분으로 가야 한다."""
    stored_first = datetime(2017, 11, 6, tzinfo=timezone.utc)
    mock_store = MagicMock()
    mock_store.get_first_candle_time.return_value = stored_first
    mock_store.get_exchange_earliest.return_value = None  # 캐시 미보유 -> 조회
    mock_store.get_last_candle_time.return_value = datetime.now(timezone.utc) - timedelta(hours=2)
    mock_binance = MagicMock()
    mock_binance.get_klines.return_value = _earliest_probe(stored_first)

    from src.pipeline import _collect_and_store_binance

    _collect_and_store_binance(mock_store, mock_binance, "SOLUSDT", timeframes=("1h",))

    # BR30: 증분도 `get_klines_since`를 쓰므로, 백필과 구분되는 신호는 "전량 재수집이 아니라
    # 마지막 저장 봉부터"라는 점이다.
    mock_binance.get_klines_since.assert_called_once()
    assert mock_binance.get_klines_since.call_args.args[2] == mock_store.get_last_candle_time.return_value


def test_binance_collection_backfills_when_the_earliest_probe_fails():
    """판단이 불가능하면 백필로 떨어진다 -- 잘못 건너뛰어 이력이 비는 것보다 한 번 더 받는 게 낫다."""
    mock_store = MagicMock()
    mock_store.get_first_candle_time.return_value = datetime(2017, 11, 6, tzinfo=timezone.utc)
    mock_store.get_last_candle_time.return_value = None  # BR29: 최신 봉이 없으니 수집 필요
    mock_store.get_exchange_earliest.return_value = None  # 캐시 미보유 -> 조회 시도 -> 실패
    mock_binance = MagicMock()
    mock_binance.get_klines.side_effect = RuntimeError("probe failed")

    from src.pipeline import _collect_and_store_binance

    _collect_and_store_binance(mock_store, mock_binance, "SOLUSDT", timeframes=("1h",))

    mock_binance.get_klines_since.assert_called_once()


def test_binance_collection_uses_incremental_once_history_is_deep_enough():
    mock_store = MagicMock()
    mock_store.get_first_candle_time.return_value = datetime.now(timezone.utc) - timedelta(
        days=settings.backtest_lookback_days + 100
    )
    mock_store.get_last_candle_time.return_value = datetime.now(timezone.utc) - timedelta(hours=2)
    mock_binance = MagicMock()
    mock_binance.get_klines.return_value = []

    from src.pipeline import _collect_and_store_binance

    _collect_and_store_binance(mock_store, mock_binance, "SOLUSDT", timeframes=("1h",))

    # 백필(target_start부터)이 아니라 증분(마지막 저장 봉부터)이어야 한다
    mock_binance.get_klines_since.assert_called_once()
    assert mock_binance.get_klines_since.call_args.args[2] == mock_store.get_last_candle_time.return_value


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


def test_earliest_probe_is_cached_so_later_runs_skip_the_request(tmp_path):
    """BR28: 거래소 최초봉은 바뀌지 않는 값이다. 캐시가 있으면 조회 없이 증분으로 간다 --
    30종 x 7봉이면 매 실행 210요청이 줄어든다."""
    from src.data_store import DataStore
    from src.pipeline import _collect_and_store_binance

    store = DataStore(str(tmp_path / "c.db"))
    stored_first = datetime(2017, 11, 6, tzinfo=timezone.utc)
    store.set_exchange_earliest("binance", "SOLUSDT", "1h", stored_first, datetime.now(timezone.utc))

    spy = MagicMock()
    spy.get_first_candle_time = MagicMock(return_value=stored_first)
    spy.get_last_candle_time = MagicMock(return_value=datetime.now(timezone.utc) - timedelta(hours=2))
    spy.get_exchange_earliest = store.get_exchange_earliest
    spy.set_exchange_earliest = store.set_exchange_earliest

    mock_binance = MagicMock()
    mock_binance.get_klines.return_value = []

    _collect_and_store_binance(spy, mock_binance, "SOLUSDT", timeframes=("1h",))

    # 최초봉 확인용 추가 요청 없이 증분 조회만 -- BR30에서 증분도 페이지네이션으로 바뀌었다
    mock_binance.get_klines.assert_not_called()
    mock_binance.get_klines_since.assert_called_once()


def test_exchange_earliest_round_trips_through_the_store(tmp_path):
    from src.data_store import DataStore

    store = DataStore(str(tmp_path / "c.db"))
    assert store.get_exchange_earliest("binance", "SOLUSDT", "4h") is None
    moment = datetime(2020, 8, 11, tzinfo=timezone.utc)
    store.set_exchange_earliest("binance", "SOLUSDT", "4h", moment, datetime.now(timezone.utc))
    assert store.get_exchange_earliest("binance", "SOLUSDT", "4h") == moment


def test_collection_is_skipped_when_no_new_bar_has_closed_yet(tmp_path):
    """BR29: 주봉은 주 1회, 월봉은 월 1회만 새 봉이 생긴다. 매시간 물어볼 이유가 없다."""
    from src.data_store import Candle, DataStore
    from src.pipeline import _collect_and_store_binance

    store = DataStore(str(tmp_path / "f.db"))
    just_closed = datetime.now(timezone.utc) - timedelta(hours=1)
    store.upsert_candles(
        "binance", "SOLUSDT", "1w",
        [Candle("SOLUSDT", "1w", just_closed - timedelta(days=7), 1, 1, 1, 1, 1.0)],
    )
    mock_binance = MagicMock()

    _collect_and_store_binance(store, mock_binance, "SOLUSDT", timeframes=("1w",))

    mock_binance.get_klines.assert_not_called()
    mock_binance.get_klines_since.assert_not_called()


def test_collection_runs_once_the_next_bar_has_closed(tmp_path):
    from src.data_store import Candle, DataStore
    from src.pipeline import _collect_and_store_binance

    store = DataStore(str(tmp_path / "f.db"))
    stale = datetime.now(timezone.utc) - timedelta(days=30)
    store.upsert_candles(
        "binance", "SOLUSDT", "1w", [Candle("SOLUSDT", "1w", stale, 1, 1, 1, 1, 1.0)]
    )
    store.set_exchange_earliest("binance", "SOLUSDT", "1w", stale, datetime.now(timezone.utc))
    mock_binance = MagicMock()
    mock_binance.get_klines_since.return_value = []

    _collect_and_store_binance(store, mock_binance, "SOLUSDT", timeframes=("1w",))

    mock_binance.get_klines_since.assert_called_once()  # 증분 조회(페이지네이션)


def test_incremental_catches_up_across_a_long_gap(tmp_path):
    """BR30: 증분이 1회 1,000봉이면 15분봉은 10일치뿐이라, 몇 년 뒤처진 타임프레임이
    영영 따라잡지 못하고 데이터에 구멍이 남는다(실측: BNB 15분봉이 2022-05에서 정지)."""
    from src.data_store import Candle, DataStore
    from src.pipeline import _collect_and_store_binance

    store = DataStore(str(tmp_path / "g.db"))
    stale = datetime.now(timezone.utc) - timedelta(days=1000)
    store.upsert_candles("binance", "SOLUSDT", "15m", [Candle("SOLUSDT", "15m", stale, 1, 1, 1, 1, 1.0)])
    store.set_exchange_earliest("binance", "SOLUSDT", "15m", stale, datetime.now(timezone.utc))

    mock_binance = MagicMock()
    mock_binance.get_klines_since.return_value = []

    _collect_and_store_binance(store, mock_binance, "SOLUSDT", timeframes=("15m",))

    # 단발 조회가 아니라 페이지네이션 경로를 써야 한다
    mock_binance.get_klines_since.assert_called_once()
    mock_binance.get_klines.assert_not_called()
