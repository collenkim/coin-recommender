from unittest.mock import MagicMock

from src.data_store import TickerInfo
from src.market_selector import BinanceMarketSelector, MarketSelector


def make_ticker(market: str, volume: float) -> TickerInfo:
    return TickerInfo(market=market, trade_price_24h=volume)


def test_excludes_btc_and_eth():
    upbit_client = MagicMock()
    upbit_client.get_tickers_by_volume.return_value = [
        make_ticker("KRW-BTC", 1_000_000),
        make_ticker("KRW-ETH", 900_000),
        make_ticker("KRW-XRP", 500_000),
    ]
    selector = MarketSelector(upbit_client, top_n=20)

    result = selector.get_candidate_markets()

    assert result == ["KRW-XRP"]


def test_returns_top_n_by_volume_descending():
    upbit_client = MagicMock()
    upbit_client.get_tickers_by_volume.return_value = [
        make_ticker("KRW-A", 100),
        make_ticker("KRW-B", 300),
        make_ticker("KRW-C", 200),
    ]
    selector = MarketSelector(upbit_client, top_n=2)

    result = selector.get_candidate_markets()

    assert result == ["KRW-B", "KRW-C"]


def test_returns_empty_list_when_no_tickers():
    upbit_client = MagicMock()
    upbit_client.get_tickers_by_volume.return_value = []
    selector = MarketSelector(upbit_client, top_n=20)

    assert selector.get_candidate_markets() == []


# --- BinanceMarketSelector (BR8) ---

def test_binance_excludes_btc_and_eth():
    binance_client = MagicMock()
    binance_client.get_tickers_by_volume.return_value = [
        make_ticker("BTCUSDT", 1_000_000),
        make_ticker("ETHUSDT", 900_000),
        make_ticker("SOLUSDT", 500_000),
    ]
    selector = BinanceMarketSelector(binance_client, top_n=20)

    result = selector.get_candidate_markets()

    assert result == ["SOLUSDT"]


def test_binance_excludes_stablecoin_pairs():
    binance_client = MagicMock()
    binance_client.get_tickers_by_volume.return_value = [
        make_ticker("USDCUSDT", 5_000_000),
        make_ticker("FDUSDUSDT", 4_000_000),
        make_ticker("SOLUSDT", 500_000),
    ]
    selector = BinanceMarketSelector(binance_client, top_n=20)

    result = selector.get_candidate_markets()

    assert result == ["SOLUSDT"]


def test_binance_excludes_leveraged_tokens():
    binance_client = MagicMock()
    binance_client.get_tickers_by_volume.return_value = [
        make_ticker("BTCUPUSDT", 2_000_000),
        make_ticker("BTCDOWNUSDT", 1_500_000),
        make_ticker("SOLUSDT", 500_000),
    ]
    selector = BinanceMarketSelector(binance_client, top_n=20)

    result = selector.get_candidate_markets()

    assert result == ["SOLUSDT"]


def test_binance_returns_top_n_by_volume_descending():
    binance_client = MagicMock()
    binance_client.get_tickers_by_volume.return_value = [
        make_ticker("AUSDT", 100),
        make_ticker("BUSDT", 300),
        make_ticker("CUSDT", 200),
    ]
    selector = BinanceMarketSelector(binance_client, top_n=2)

    result = selector.get_candidate_markets()

    assert result == ["BUSDT", "CUSDT"]
