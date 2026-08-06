from datetime import datetime, timezone
from unittest.mock import MagicMock, patch

import pandas as pd
import pytest
import requests

from src.upbit_client import UpbitClient


def make_ohlcv_df() -> pd.DataFrame:
    index = pd.to_datetime(["2024-01-01 09:00:00", "2024-01-01 10:00:00"])  # KST wall-clock, tz-naive
    return pd.DataFrame(
        {
            "open": [100.0, 101.0],
            "high": [110.0, 111.0],
            "low": [90.0, 91.0],
            "close": [105.0, 106.0],
            "volume": [1000.0, 1100.0],
        },
        index=index,
    )


def test_get_ohlcv_converts_kst_to_utc():
    client = UpbitClient(request_delay_seconds=0)
    with patch("src.upbit_client.pyupbit.get_ohlcv", return_value=make_ohlcv_df()) as mock_fetch:
        candles = client.get_ohlcv("KRW-XRP", "1h", count=2)

    mock_fetch.assert_called_once()
    assert len(candles) == 2
    # 2024-01-01 09:00 KST == 2024-01-01 00:00 UTC
    assert candles[0].candle_time == datetime(2024, 1, 1, 0, 0, tzinfo=timezone.utc)
    assert candles[0].market == "KRW-XRP"
    assert candles[0].timeframe == "1h"
    assert candles[0].close == 105.0


def test_get_ohlcv_returns_empty_list_when_no_data():
    client = UpbitClient(request_delay_seconds=0)
    with patch("src.upbit_client.pyupbit.get_ohlcv", return_value=pd.DataFrame()):
        assert client.get_ohlcv("KRW-XRP", "1h", count=100) == []


def test_get_ohlcv_retries_on_connection_error_then_succeeds():
    client = UpbitClient(request_delay_seconds=0, max_retries=3)
    side_effects = [requests.ConnectionError("boom"), make_ohlcv_df()]
    with patch("src.upbit_client.pyupbit.get_ohlcv", side_effect=side_effects), \
         patch("src.upbit_client.time.sleep") as mock_sleep:
        candles = client.get_ohlcv("KRW-XRP", "1h", count=2)

    assert len(candles) == 2
    # sleep is called both for the retry backoff (1.0s) and the post-fetch rate-limit
    # delay (request_delay_seconds=0 here) -- assert the backoff call specifically.
    assert mock_sleep.call_args_list[0].args == (1.0,)


def test_get_ohlcv_gives_up_after_max_retries():
    client = UpbitClient(request_delay_seconds=0, max_retries=2)
    with patch("src.upbit_client.pyupbit.get_ohlcv", side_effect=requests.ConnectionError("boom")), \
         patch("src.upbit_client.time.sleep"):
        with pytest.raises(requests.ConnectionError):
            client.get_ohlcv("KRW-XRP", "1h", count=2)


def test_get_tickers_by_volume_parses_response():
    client = UpbitClient()
    mock_response = MagicMock()
    mock_response.json.return_value = [
        {"market": "KRW-XRP", "acc_trade_price_24h": 123456.0},
        {"market": "KRW-DOGE", "acc_trade_price_24h": 654321.0},
    ]
    mock_response.raise_for_status.return_value = None

    with patch("src.upbit_client.pyupbit.get_tickers", return_value=["KRW-XRP", "KRW-DOGE"]), \
         patch("src.upbit_client.requests.get", return_value=mock_response) as mock_get:
        tickers = client.get_tickers_by_volume()

    mock_get.assert_called_once()
    assert len(tickers) == 2
    assert tickers[0].market == "KRW-XRP"
    assert tickers[0].trade_price_24h == 123456.0


def test_get_tickers_by_volume_returns_empty_when_no_markets():
    client = UpbitClient()
    with patch("src.upbit_client.pyupbit.get_tickers", return_value=[]):
        assert client.get_tickers_by_volume() == []
