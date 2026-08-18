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


# --- get_tickers_by_volume (BR8) ---

def test_get_tickers_by_volume_keeps_only_usdt_pairs():
    client = BinanceClient()
    payload = [
        {"symbol": "BTCUSDT", "quoteVolume": "123456.0"},
        {"symbol": "ETHBTC", "quoteVolume": "999999.0"},
        {"symbol": "SOLUSDT", "quoteVolume": "654321.0"},
    ]
    with patch("src.binance_client.requests.get", return_value=mock_response(payload)) as mock_get:
        tickers = client.get_tickers_by_volume()

    mock_get.assert_called_once()
    assert [t.market for t in tickers] == ["BTCUSDT", "SOLUSDT"]
    assert tickers[0].trade_price_24h == 123456.0


def test_get_tickers_by_volume_returns_empty_when_no_data():
    client = BinanceClient()
    with patch("src.binance_client.requests.get", return_value=mock_response([])):
        assert client.get_tickers_by_volume() == []


# --- get_klines_since (pagination past Binance's 1000-candle response cap) ---

HOUR_MS = 3_600_000


def kline_at(ts_ms: int) -> list:
    return [ts_ms, "100.0", "110.0", "90.0", "105.0", "1000.0", 0, "0", 0, "0", "0", "0"]


def test_get_klines_since_pages_past_the_response_cap():
    """A full page means there may be more; Binance re-sends the startTime candle, so overlap must
    be dropped rather than duplicated. _MAX_LIMIT is patched small to keep the fixture readable."""
    client = BinanceClient()
    page1 = [kline_at(0), kline_at(HOUR_MS)]  # full page -> keep going
    page2 = [kline_at(HOUR_MS), kline_at(2 * HOUR_MS)]  # first item overlaps page1's last
    page3 = [kline_at(2 * HOUR_MS)]  # only the overlap left -> stop

    with patch("src.binance_client._MAX_LIMIT", 2), \
         patch("src.binance_client.requests.get",
               side_effect=[mock_response(page1), mock_response(page2), mock_response(page3)]) as mock_get:
        candles = client.get_klines_since("BTCUSDT", "1h", datetime.fromtimestamp(0, tz=timezone.utc))

    assert mock_get.call_count == 3
    assert [int(c.candle_time.timestamp() * 1000) for c in candles] == [0, HOUR_MS, 2 * HOUR_MS]


def test_get_klines_since_stops_immediately_on_a_short_page():
    client = BinanceClient()
    with patch("src.binance_client._MAX_LIMIT", 100), \
         patch("src.binance_client.requests.get", return_value=mock_response([kline_at(0)])) as mock_get:
        candles = client.get_klines_since("BTCUSDT", "1h", datetime.fromtimestamp(0, tz=timezone.utc))

    mock_get.assert_called_once()
    assert len(candles) == 1


def test_get_klines_since_returns_empty_when_no_history():
    client = BinanceClient()
    with patch("src.binance_client.requests.get", return_value=mock_response([])):
        assert client.get_klines_since("BTCUSDT", "1h", datetime.fromtimestamp(0, tz=timezone.utc)) == []


def test_pagination_guard_covers_the_configured_lookback():
    """상한이 모자라면 예외 없이 조용히 잘려, 설정한 lookback보다 짧은 이력으로 백테스트가 돈다.
    12년치 1시간봉 = 105,120봉 = 106페이지."""
    from src.binance_client import _MAX_LIMIT, _MAX_PAGES
    from src.config import settings

    needed_pages = settings.backtest_lookback_days * 24 / _MAX_LIMIT
    assert _MAX_PAGES > needed_pages, f"{_MAX_PAGES}페이지로는 {needed_pages:.0f}페이지가 필요한 lookback을 못 채운다"
