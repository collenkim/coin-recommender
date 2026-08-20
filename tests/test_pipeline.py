from datetime import datetime, timedelta, timezone
from unittest.mock import MagicMock, patch

import pytest

from src.backtest import STRONG_BULL
from src.config import settings
from src.data_store import STOP_HIT, TARGET_HIT
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


def test_shallow_history_is_backfilled_even_when_the_latest_bar_is_current():
    """BR41: `_is_up_to_date`는 **마지막 봉만** 본다. 최신봉만 있으면 그대로 건너뛰므로 앞이 얕은
    종목은 영원히 깊어지지 않는다 -- lookback을 늘린 직후가 정확히 이 상태다(꼬리는 최신, 머리는 얕음).

    "최신봉이 있으니 완료"는 "최초봉이 있으니 완료"와 같은 계열의 오판이다."""
    mock_store = MagicMock()
    stored_first = datetime.now(timezone.utc) - timedelta(days=365)
    mock_store.get_first_candle_time.return_value = stored_first
    mock_store.get_last_candle_time.return_value = datetime.now(timezone.utc) - timedelta(minutes=10)
    # 거래소는 2017년부터 갖고 있다 -- 아직 8년어치를 더 받을 수 있다.
    mock_store.get_exchange_earliest.return_value = datetime(2017, 11, 6, tzinfo=timezone.utc)
    mock_binance = MagicMock()

    from src.pipeline import _collect_and_store_binance

    _collect_and_store_binance(mock_store, mock_binance, "SOLUSDT", timeframes=("1h",))

    mock_binance.get_klines_since.assert_called_once()
    # 증분(마지막 봉부터)이면 앞의 구멍이 그대로 남는다 -- 백필이어야 한다.
    assert mock_binance.get_klines_since.call_args.args[2] < stored_first


def test_fresh_and_deep_history_is_still_skipped_without_any_request():
    """BR29는 유지된다 -- 깊이까지 채워진 종목은 새 봉이 마감되기 전까지 조회하지 않는다."""
    mock_store = MagicMock()
    stored_first = datetime(2017, 11, 6, tzinfo=timezone.utc)
    mock_store.get_first_candle_time.return_value = stored_first
    mock_store.get_last_candle_time.return_value = datetime.now(timezone.utc) - timedelta(minutes=10)
    mock_store.get_exchange_earliest.return_value = stored_first
    mock_binance = MagicMock()

    from src.pipeline import _collect_and_store_binance

    _collect_and_store_binance(mock_store, mock_binance, "SOLUSDT", timeframes=("1h",))

    mock_binance.get_klines_since.assert_not_called()
    mock_binance.get_klines.assert_not_called()


# --- evaluate_pending_outcomes (BR9) ---

def _store_with(tmp_path, track, target_hit=None, stop_hit=None, entry_time=None):
    from src.data_store import DataStore

    store = DataStore(str(tmp_path / "e.db"))
    entry = entry_time or datetime(2026, 8, 20, tzinfo=timezone.utc)

    class R:
        market = "SOLUSDT"
        expected_return = 0.01
        n = 100
        hit_count = 30
        source = "binance"
        entry_price = 100.0
        max_drawdown = -0.01

    R.track = track
    R.entry_time = entry
    store.save_run(entry, True, [R()])
    if target_hit:
        store.mark_price_event(entry, "SOLUSDT", TARGET_HIT, target_hit, track)
    if stop_hit:
        store.mark_price_event(entry, "SOLUSDT", STOP_HIT, stop_hit, track)
    return store, entry


def test_outcome_is_derived_from_the_monitor_record_not_rejudged(tmp_path):
    """BR39: 이전에는 사후 판정이 1시간봉으로 레거시 규칙(+3%/-2%/24h)을 적용해 **모든 트랙을
    같은 기준으로** 판정했다. 감시는 1분봉으로 트랙별 목표를 보므로 둘이 어긋날 수밖에 없었다."""
    from src.data_store import TARGET_HIT
    from src.pipeline import evaluate_pending_outcomes
    from src.tracks import TRACK_BY_KEY

    store, entry = _store_with(tmp_path, "long", target_hit=datetime(2026, 8, 20, 5, tzinfo=timezone.utc))
    evaluate_pending_outcomes(store, entry + timedelta(hours=60))

    run = store.get_latest_run()
    rec = run.recommendations[0]
    assert rec.target_reached is True
    assert rec.realized_return == TRACK_BY_KEY["long"].target  # 레거시 3%가 아니라 장기 10%


def test_stop_hit_is_recorded_with_the_track_stop(tmp_path):
    from src.data_store import STOP_HIT
    from src.pipeline import evaluate_pending_outcomes
    from src.tracks import TRACK_BY_KEY

    store, entry = _store_with(tmp_path, "mid", stop_hit=datetime(2026, 8, 20, 1, tzinfo=timezone.utc))
    evaluate_pending_outcomes(store, entry + timedelta(hours=30))

    rec = store.get_latest_run().recommendations[0]
    assert rec.target_reached is False
    assert rec.realized_return == -TRACK_BY_KEY["mid"].stop  # 레거시 -2%가 아니라 중기 -4%


def test_in_progress_recommendations_are_left_unevaluated(tmp_path):
    """보유 창이 지나기 전에 판정하면 BR24의 '미완료 매매 집계' 결함이 반복된다."""
    from src.pipeline import evaluate_pending_outcomes

    store, entry = _store_with(tmp_path, "long")  # 도달 없음
    evaluate_pending_outcomes(store, entry + timedelta(hours=10))  # 장기 창은 48시간

    assert store.get_latest_run().recommendations[0].target_reached is None


def test_evaluation_isolates_per_item_failure(tmp_path):
    from unittest.mock import patch

    from src.pipeline import evaluate_pending_outcomes

    store, entry = _store_with(tmp_path, "day")
    with patch.object(type(store), "record_track_outcome", side_effect=RuntimeError("db down")):
        evaluate_pending_outcomes(store, entry + timedelta(hours=30))  # 예외가 새어나오지 않아야 한다

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
    first = just_closed - timedelta(days=7)
    store.upsert_candles("binance", "SOLUSDT", "1w", [Candle("SOLUSDT", "1w", first, 1, 1, 1, 1, 1.0)])
    # BR41: 건너뛰려면 깊이도 다 차 있어야 한다. 보유 최초봉이 거래소 최초봉임을 캐시로 알린다.
    store.set_exchange_earliest("binance", "SOLUSDT", "1w", first, datetime.now(timezone.utc))
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


def test_already_announced_entries_are_not_notified_again(tmp_path):
    """BR31: 진입 신호는 4시간봉 하나를 가리키는데 파이프라인은 30분마다 돈다.
    억제가 없으면 같은 추천이 최대 8회 발송된다(실측 확인)."""
    from src.data_store import DataStore
    from src.pipeline import _drop_already_announced

    store = DataStore(str(tmp_path / "d.db"))
    entry = datetime(2026, 8, 18, 16, tzinfo=timezone.utc)

    class R:
        market = "XRPUSDT"
        expected_return = 0.01
        n = 100
        hit_count = 30
        source = "binance"
        entry_price = 1.0
        max_drawdown = -0.01
        track = "ultra"
        entry_time = entry

    store.save_run(datetime.now(timezone.utc), True, [R()])
    announced = store.get_announced_entries(datetime.now(timezone.utc) - timedelta(days=10))

    assert (R.market, "ultra", entry.isoformat()) in announced
    assert _drop_already_announced([R()], announced) == []


def test_a_new_entry_bar_is_still_notified(tmp_path):
    """억제는 '같은 진입봉'에만 걸려야 한다 -- 다음 교차는 정상 발송되어야 한다."""
    from src.data_store import DataStore
    from src.pipeline import _drop_already_announced

    store = DataStore(str(tmp_path / "d.db"))

    class R:
        market = "XRPUSDT"
        expected_return = 0.01
        n = 100
        hit_count = 30
        source = "binance"
        entry_price = 1.0
        max_drawdown = -0.01
        track = "ultra"
        entry_time = datetime(2026, 8, 18, 16, tzinfo=timezone.utc)

    store.save_run(datetime.now(timezone.utc), True, [R()])
    announced = store.get_announced_entries(datetime.now(timezone.utc) - timedelta(days=10))

    class Next(R):
        entry_time = datetime(2026, 8, 18, 20, tzinfo=timezone.utc)  # 다음 4시간봉

    assert len(_drop_already_announced([Next()], announced)) == 1


def test_scheduler_runs_every_30_minutes():
    from src.scheduler import _JOB_ID, start_scheduler, stop_scheduler
    from fastapi import FastAPI

    app = FastAPI()
    scheduler = start_scheduler(app)
    try:
        job = scheduler.get_job(_JOB_ID)
        minute = next(f for f in job.trigger.fields if f.name == "minute")
        assert str(minute) == "5,35"
    finally:
        stop_scheduler(app)
