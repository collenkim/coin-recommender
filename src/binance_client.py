import time
from datetime import datetime, timezone
from typing import Callable, TypeVar

import requests

from src.data_store import Candle, TickerInfo

_BINANCE_KLINES_URL = "https://api.binance.com/api/v3/klines"
_BINANCE_TICKER_24HR_URL = "https://api.binance.com/api/v3/ticker/24hr"
_MAX_LIMIT = 1000

T = TypeVar("T")


def _retry_with_backoff(fn: Callable[[], T], max_attempts: int = 3, base_delay: float = 1.0) -> T:
    """Retries fn on transient errors with exponential backoff (1s, 2s, 4s).
    Does not retry on 4xx client errors (RESILIENCY-10 / NFR Design)."""
    for attempt in range(max_attempts):
        try:
            return fn()
        except requests.HTTPError as exc:
            status = exc.response.status_code if exc.response is not None else None
            if status is not None and 400 <= status < 500:
                raise
            if attempt == max_attempts - 1:
                raise
            time.sleep(base_delay * (2**attempt))
        except (requests.Timeout, requests.ConnectionError):
            if attempt == max_attempts - 1:
                raise
            time.sleep(base_delay * (2**attempt))
    raise RuntimeError("unreachable")


class BinanceClient:
    def __init__(self, timeout_seconds: float = 10.0, max_retries: int = 3):
        self._timeout = timeout_seconds
        self._max_retries = max_retries

    def get_klines(
        self,
        symbol: str,
        interval: str,
        start_time: datetime | None = None,
        limit: int = 100,
    ) -> list[Candle]:
        params = {"symbol": symbol, "interval": interval, "limit": min(limit, _MAX_LIMIT)}
        if start_time is not None:
            params["startTime"] = int(start_time.timestamp() * 1000)

        def fetch():
            response = requests.get(_BINANCE_KLINES_URL, params=params, timeout=self._timeout)
            response.raise_for_status()
            return response.json()

        raw = _retry_with_backoff(fetch, max_attempts=self._max_retries)

        return [
            Candle(
                market=symbol,
                timeframe=interval,
                candle_time=datetime.fromtimestamp(item[0] / 1000, tz=timezone.utc),
                open=float(item[1]),
                high=float(item[2]),
                low=float(item[3]),
                close=float(item[4]),
                volume=float(item[5]),
            )
            for item in raw
        ]

    def get_tickers_by_volume(self) -> list[TickerInfo]:
        """24h ticker stats for every symbol on the exchange (public endpoint, no market-list lookup
        needed first, unlike Upbit). Only USDT-quoted symbols are returned -- mixing quote currencies
        into a single trade_price_24h ranking would not be a meaningful comparison."""

        def fetch():
            response = requests.get(_BINANCE_TICKER_24HR_URL, timeout=self._timeout)
            response.raise_for_status()
            return response.json()

        raw = _retry_with_backoff(fetch, max_attempts=self._max_retries)
        return [
            TickerInfo(market=item["symbol"], trade_price_24h=float(item["quoteVolume"]))
            for item in raw
            if item["symbol"].endswith("USDT")
        ]
