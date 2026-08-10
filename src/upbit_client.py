import logging
import time
from datetime import datetime, timedelta, timezone
from typing import Callable, TypeVar

import pyupbit
import requests

from src.data_store import Candle, TickerInfo, drop_unclosed

logger = logging.getLogger(__name__)

_KST = timezone(timedelta(hours=9))
_TIMEFRAME_TO_PYUPBIT_INTERVAL = {"1h": "minute60", "4h": "minute240"}
_UPBIT_TICKER_URL = "https://api.upbit.com/v1/ticker"

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


def _to_utc(kst_naive_dt: datetime) -> datetime:
    """pyupbit returns candle timestamps as KST wall-clock time (tz-naive); normalize to UTC (BR6)."""
    return kst_naive_dt.replace(tzinfo=_KST).astimezone(timezone.utc)


class UpbitClient:
    def __init__(self, timeout_seconds: float = 10.0, max_retries: int = 3, request_delay_seconds: float = 0.1):
        self._timeout = timeout_seconds
        self._max_retries = max_retries
        self._request_delay = request_delay_seconds

    def get_ohlcv(self, market: str, timeframe: str, count: int, to: datetime | None = None) -> list[Candle]:
        interval = _TIMEFRAME_TO_PYUPBIT_INTERVAL[timeframe]
        to_str = to.strftime("%Y-%m-%d %H:%M:%S") if to is not None else None

        def fetch():
            return pyupbit.get_ohlcv(market, interval=interval, count=count, to=to_str)

        df = _retry_with_backoff(fetch, max_attempts=self._max_retries)
        time.sleep(self._request_delay)

        if df is None or df.empty:
            return []

        candles = [
            Candle(
                market=market,
                timeframe=timeframe,
                candle_time=_to_utc(index.to_pydatetime()),
                open=float(row["open"]),
                high=float(row["high"]),
                low=float(row["low"]),
                close=float(row["close"]),
                volume=float(row["volume"]),
            )
            for index, row in df.iterrows()
        ]
        return drop_unclosed(candles)

    def get_tickers_by_volume(self) -> list[TickerInfo]:
        markets = pyupbit.get_tickers(fiat="KRW")
        if not markets:
            return []

        def fetch():
            response = requests.get(
                _UPBIT_TICKER_URL,
                params={"markets": ",".join(markets)},
                timeout=self._timeout,
            )
            response.raise_for_status()
            return response.json()

        data = _retry_with_backoff(fetch, max_attempts=self._max_retries)
        return [TickerInfo(market=item["market"], trade_price_24h=float(item["acc_trade_price_24h"])) for item in data]
