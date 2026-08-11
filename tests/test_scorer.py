from datetime import datetime, timedelta, timezone
from unittest.mock import patch

from src.backtest import MIN_HIT_RATE, MIN_SIGNAL_SAMPLES, REGIME_BARS_30D, STRONG_BULL, SignalStats
from src.data_store import Candle, DataStore
from src.scorer import BTC_MARKET, REGIME_TIMEFRAME, SOURCE, check_market_regime, generate_recommendations

UTC = timezone.utc
T0 = datetime(2024, 1, 1, tzinfo=UTC)


def make_store(tmp_path) -> DataStore:
    return DataStore(str(tmp_path / "test.db"))


def candle(market: str, i: int, close: float, timeframe="1h") -> Candle:
    return Candle(
        market=market,
        timeframe=timeframe,
        candle_time=T0 + timedelta(hours=i * (4 if timeframe == "4h" else 1)),
        open=close,
        high=close,
        low=close,
        close=close,
        volume=100.0,
    )


def seed_strong_bull(store: DataStore) -> None:
    closes = [100.0] + [100.0 + i * 0.2 for i in range(REGIME_BARS_30D)]
    store.upsert_candles(SOURCE, BTC_MARKET, REGIME_TIMEFRAME, [candle(BTC_MARKET, i, c, "4h") for i, c in enumerate(closes)])


def seed_flat_regime(store: DataStore) -> None:
    closes = [100.0] * (REGIME_BARS_30D + 1)
    store.upsert_candles(SOURCE, BTC_MARKET, REGIME_TIMEFRAME, [candle(BTC_MARKET, i, c, "4h") for i, c in enumerate(closes)])


def seed_market(store: DataStore, market: str, bars: int = 60) -> None:
    store.upsert_candles(SOURCE, market, "1h", [candle(market, i, 100.0) for i in range(bars)])


def stats(n=5, hit_count=3, hit_rate=None, lower=0.3) -> SignalStats:
    return SignalStats(
        market="X",
        n=n,
        hit_count=hit_count,
        hit_rate=hit_count / n if hit_rate is None else hit_rate,
        hit_rate_lower=lower,
        expected_return=0.01,
        max_drawdown=-0.02,
    )


# --- check_market_regime (BR20) ---

def test_check_market_regime_reports_the_named_regime(tmp_path):
    store = make_store(tmp_path)
    seed_strong_bull(store)
    assert check_market_regime(store) == STRONG_BULL


def test_check_market_regime_is_none_in_a_flat_market(tmp_path):
    store = make_store(tmp_path)
    seed_flat_regime(store)
    assert check_market_regime(store) is None


def test_check_market_regime_is_none_without_btc_history(tmp_path):
    """BTC 수집이 실패했을 때 레짐을 모른 채 진입하지 않는다."""
    assert check_market_regime(make_store(tmp_path)) is None


# --- generate_recommendations (BR13/BR21) ---

def test_no_recommendations_outside_the_allowed_regimes(tmp_path):
    store = make_store(tmp_path)
    seed_flat_regime(store)
    seed_market(store, "AAAUSDT")
    with patch("src.scorer.entry_signal", return_value=True), patch("src.scorer.compute_signal_stats", return_value=stats()):
        assert generate_recommendations(["AAAUSDT"], store) == []


def test_recommends_a_market_that_passes_regime_signal_and_sample_floor(tmp_path):
    store = make_store(tmp_path)
    seed_strong_bull(store)
    seed_market(store, "AAAUSDT")
    with patch("src.scorer.entry_signal", return_value=True), patch("src.scorer.compute_signal_stats", return_value=stats()):
        result = generate_recommendations(["AAAUSDT"], store)
    assert [r.market for r in result] == ["AAAUSDT"]
    assert result[0].source == "binance"
    assert result[0].entry_price == 100.0


def test_market_without_a_live_entry_signal_is_skipped(tmp_path):
    store = make_store(tmp_path)
    seed_strong_bull(store)
    seed_market(store, "AAAUSDT")
    with patch("src.scorer.entry_signal", return_value=False), patch("src.scorer.compute_signal_stats", return_value=stats()):
        assert generate_recommendations(["AAAUSDT"], store) == []


def test_market_below_the_sample_floor_is_skipped(tmp_path):
    store = make_store(tmp_path)
    seed_strong_bull(store)
    seed_market(store, "AAAUSDT")
    thin = stats(n=MIN_SIGNAL_SAMPLES - 1, hit_count=MIN_SIGNAL_SAMPLES - 1)
    with patch("src.scorer.entry_signal", return_value=True), patch("src.scorer.compute_signal_stats", return_value=thin):
        assert generate_recommendations(["AAAUSDT"], store) == []


def test_market_below_the_hit_rate_floor_is_skipped(tmp_path):
    store = make_store(tmp_path)
    seed_strong_bull(store)
    seed_market(store, "AAAUSDT")
    weak = stats(n=10, hit_count=1)  # 10%, MIN_HIT_RATE 미만
    assert weak.hit_rate < MIN_HIT_RATE
    with patch("src.scorer.entry_signal", return_value=True), patch("src.scorer.compute_signal_stats", return_value=weak):
        assert generate_recommendations(["AAAUSDT"], store) == []


def test_recommendations_are_ranked_by_confidence_lower_bound_not_raw_hit_rate(tmp_path):
    """표본 3건에 3승(적중률 100%)이 표본 20건에 14승보다 위에 오면 안 된다."""
    store = make_store(tmp_path)
    seed_strong_bull(store)
    seed_market(store, "THINUSDT")
    seed_market(store, "DEEPUSDT")
    thin = stats(n=3, hit_count=3, lower=0.44)
    deep = stats(n=20, hit_count=14, lower=0.48)
    with patch("src.scorer.entry_signal", return_value=True), patch(
        "src.scorer.compute_signal_stats", side_effect=[thin, deep]
    ):
        result = generate_recommendations(["THINUSDT", "DEEPUSDT"], store)
    assert [r.market for r in result] == ["DEEPUSDT", "THINUSDT"]
    assert result[0].hit_rate < result[1].hit_rate  # 원시 적중률로는 역순
