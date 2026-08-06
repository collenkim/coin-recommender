from datetime import datetime, timezone
from unittest.mock import MagicMock, patch

import pytest
import requests

from src.binance_client import BinanceClient


def make_raw_klines() -> list:
    # [open_time_ms, open, high, low, close, volume, ...]
    return [
        [1704067200000, "100.0", "110.0", "90.0", "105.0", "1000.0", 0, "0", 0, "0", "0", "0"],
        [1704081600000, "101.0", "111.0", "91.0", "106.0", "1100.0", 0, "0", 0, "0", "0", "0"],
    ]


def mock_response(payload):
    response = MagicMock()
    response.json.return_value = payload
    response.raise_for_status.return_value = None
    return response


def test_get_klines_parses_response_to_candles():
    client = BinanceClient()
    with patch("src.binance_client.requests.get", return_value=mock_response(make_raw_klines())) as mock_get:
        candles = client.get_klines("BTCUSDT", "4h", limit=2)

    mock_get.assert_called_once()
    assert len(candles) == 2
    assert candles[0].market == "BTCUSDT"
    assert candles[0].timeframe == "4h"
    assert candles[0].candle_time == datetime.fromtimestamp(1704067200000 / 1000, tz=timezone.utc)
    assert candles[0].close == 105.0


def test_get_klines_includes_start_time_param_when_given():
    client = BinanceClient()
    start = datetime(2024, 1, 1, tzinfo=timezone.utc)
    with patch("src.binance_client.requests.get", return_value=mock_response([])) as mock_get:
        client.get_klines("BTCUSDT", "4h", start_time=start, limit=10)

    _, kwargs = mock_get.call_args
    assert kwargs["params"]["startTime"] == int(start.timestamp() * 1000)


def test_get_klines_retries_on_5xx_then_succeeds():
    client = BinanceClient(max_retries=3)
    error_response = MagicMock()
    http_error = requests.HTTPError(response=MagicMock(status_code=503))
    error_response.raise_for_status.side_effect = http_error

    with patch(
        "src.binance_client.requests.get",
        side_effect=[error_response, mock_response(make_raw_klines())],
    ), patch("src.binance_client.time.sleep") as mock_sleep:
        candles = client.get_klines("BTCUSDT", "4h", limit=2)

    assert len(candles) == 2
    mock_sleep.assert_called_once()


def test_get_klines_does_not_retry_on_4xx():
    client = BinanceClient(max_retries=3)
    error_response = MagicMock()
    http_error = requests.HTTPError(response=MagicMock(status_code=400))
    error_response.raise_for_status.side_effect = http_error

    with patch("src.binance_client.requests.get", return_value=error_response) as mock_get, \
         patch("src.binance_client.time.sleep") as mock_sleep:
        with pytest.raises(requests.HTTPError):
            client.get_klines("BTCUSDT", "4h", limit=2)

    mock_get.assert_called_once()
    mock_sleep.assert_not_called()
