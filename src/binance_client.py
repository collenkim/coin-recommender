import logging
import time
from datetime import datetime, timezone
from typing import Callable, TypeVar

import requests

from src.data_store import Candle, TickerInfo, drop_unclosed

logger = logging.getLogger(__name__)

_BINANCE_KLINES_URL = "https://api.binance.com/api/v3/klines"
_BINANCE_TICKER_24HR_URL = "https://api.binance.com/api/v3/ticker/24hr"
_MAX_LIMIT = 1000
# 폭주 방지 상한. **가장 짧은 봉 × 그 봉의 lookback**이 기준이다 -- 모자라면 예외 없이 조용히
# 잘려서, 설정한 lookback보다 짧은 이력으로 백테스트가 돌아간다.
# 16년치 15분봉이 560,640개(561페이지)로 현재 최대 요구치다(30분봉 281, 1시간봉 141).
# 60 -> 130 -> 150 -> 300 -> 600으로 올려 왔다. lookback이나 수집 타임프레임을 바꿀 때는
# 반드시 함께 확인한다 -- `test_pagination_guard_covers_every_collected_timeframe`이 검사한다.
_MAX_PAGES = 600

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

        candles = [
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
        return drop_unclosed(candles)

    def get_klines_since(self, symbol: str, interval: str, start_time: datetime, max_requests: int = _MAX_PAGES) -> list[Candle]:
        """Paginated history fetch from `start_time` to now.

        Binance returns at most _MAX_LIMIT candles per response, and `get_klines` clamps to that
        silently -- which is why stored Binance history sat at ~1000 bars (41 days of 1h) even
        though backtest_lookback_days was 180. This walks forward until the exchange stops
        returning new candles, so the configured lookback is actually honoured.

        `max_requests` is a runaway guard. It must exceed what the configured lookback needs --
        5 years of 1h bars is 43,800 candles (44 pages), and a guard set below that truncates
        silently, leaving the backtest running on less history than configured.
        """
        collected: list[Candle] = []
        cursor = start_time
        for _ in range(max_requests):
            raw = self.get_klines(symbol, interval, start_time=cursor, limit=_MAX_LIMIT)
            if not raw:
                break
            # Binance includes the candle at `startTime`, so drop anything we already hold.
            fresh = [c for c in raw if not collected or c.candle_time > collected[-1].candle_time]
            if not fresh:
                break
            collected.extend(fresh)
            if len(raw) < _MAX_LIMIT:
                break  # short page -- the exchange has nothing more
            cursor = collected[-1].candle_time
        else:
            # BR41: 상한에 걸려 끊긴 것을 조용히 넘기면 "받을 만큼 받았다"로 보인다. 다음 실행이
            # 이어받아 메우지만(꼬리가 뒤처지므로 증분이 돈다), 몇 회차 동안 얕은 이력으로 확률을
            # 계산하게 되므로 드러나야 한다.
            logger.warning(
                "get_klines_since hit the %d-page guard for %s %s (%d bars from %s) -- history is truncated this run",
                max_requests, symbol, interval, len(collected), start_time,
            )
        return collected

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
