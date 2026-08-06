from datetime import datetime, timezone
from unittest.mock import MagicMock, patch

from src.backtest import SignalStats
from src.data_store import Candle, DataStore
from src.features import IchimokuPoint
from src.scorer import check_market_regime, generate_recommendations

UTC = timezone.utc
NOW = datetime(2024, 6, 1, tzinfo=UTC)


def make_store(tmp_path) -> DataStore:
    return DataStore(str(tmp_path / "test.db"))


def bullish_point(hour=0) -> IchimokuPoint:
    return IchimokuPoint(datetime(2024, 1, 1, hour, tzinfo=UTC), close=100.0, tenkan=1, kijun=1, senkou_a=10.0, senkou_b=5.0)


def bearish_point(hour=0) -> IchimokuPoint:
    return IchimokuPoint(datetime(2024, 1, 1, hour, tzinfo=UTC), close=1.0, tenkan=1, kijun=1, senkou_a=5.0, senkou_b=10.0)


# --- check_market_regime ---

def test_check_market_regime_true_when_both_btc_and_eth_bullish(tmp_path):
    store = make_store(tmp_path)
    with patch("src.scorer.compute_ichimoku", side_effect=[[bullish_point()], [bullish_point()]]):
        assert check_market_regime(store) is True


def test_check_market_regime_false_when_only_btc_bullish(tmp_path):
    store = make_store(tmp_path)
    with patch("src.scorer.compute_ichimoku", side_effect=[[bullish_point()], [bearish_point()]]):
        assert check_market_regime(store) is False


def test_check_market_regime_false_when_no_data(tmp_path):
    store = make_store(tmp_path)
    with patch("src.scorer.compute_ichimoku", side_effect=[[], []]):
        assert check_market_regime(store) is False


# --- generate_recommendations ---

def test_generate_recommendations_returns_empty_when_regime_not_bullish(tmp_path):
    store = make_store(tmp_path)
    with patch("src.scorer.check_market_regime", return_value=False), \
         patch("src.scorer.compute_ichimoku") as mock_compute:
        result = generate_recommendations(["KRW-XRP"], store, NOW)

    assert result == []
    mock_compute.assert_not_called()  # short-circuits before touching candidates


def test_generate_recommendations_skips_candidate_without_current_signal(tmp_path):
    store = make_store(tmp_path)
    with patch("src.scorer.check_market_regime", return_value=True), \
         patch("src.scorer.compute_ichimoku", return_value=[bullish_point()]), \
         patch("src.scorer._composite_signal_on_latest_bar", return_value=False), \
         patch("src.scorer.compute_signal_stats") as mock_stats:
        result = generate_recommendations(["KRW-XRP"], store, NOW)

    assert result == []
    mock_stats.assert_not_called()


def test_generate_recommendations_excludes_below_threshold(tmp_path):
    store = make_store(tmp_path)
    with patch("src.scorer.check_market_regime", return_value=True), \
         patch("src.scorer.compute_ichimoku", return_value=[bullish_point()]), \
         patch("src.scorer._composite_signal_on_latest_bar", return_value=True), \
         patch("src.scorer.compute_signal_stats", return_value=SignalStats("KRW-XRP", 0.03, 5, 1)):
        result = generate_recommendations(["KRW-XRP"], store, NOW)

    assert result == []


def test_generate_recommendations_excludes_n_zero(tmp_path):
    store = make_store(tmp_path)
    with patch("src.scorer.check_market_regime", return_value=True), \
         patch("src.scorer.compute_ichimoku", return_value=[bullish_point()]), \
         patch("src.scorer._composite_signal_on_latest_bar", return_value=True), \
         patch("src.scorer.compute_signal_stats", return_value=SignalStats("KRW-XRP", None, 0, 0)):
        result = generate_recommendations(["KRW-XRP"], store, NOW)

    assert result == []


def test_generate_recommendations_includes_and_sorts_by_expected_return_desc(tmp_path):
    store = make_store(tmp_path)
    stats_by_market = {
        "KRW-A": SignalStats("KRW-A", 0.05, 3, 1),
        "KRW-B": SignalStats("KRW-B", 0.09, 4, 2),
    }

    def fake_stats(market, *args, **kwargs):
        return stats_by_market[market]

    with patch("src.scorer.check_market_regime", return_value=True), \
         patch("src.scorer.compute_ichimoku", return_value=[bullish_point()]), \
         patch("src.scorer._composite_signal_on_latest_bar", return_value=True), \
         patch("src.scorer.compute_signal_stats", side_effect=fake_stats):
        result = generate_recommendations(["KRW-A", "KRW-B"], store, NOW)

    assert [r.market for r in result] == ["KRW-B", "KRW-A"]
    assert result[0].expected_return == 0.09
    assert result[0].n == 4
    assert result[0].hit_count == 2
