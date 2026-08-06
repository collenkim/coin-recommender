from unittest.mock import MagicMock

from src.market_selector import MarketSelector
from src.upbit_client import TickerInfo


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
