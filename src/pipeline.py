import logging
import threading
from dataclasses import dataclass
from datetime import datetime, timezone

from src.binance_client import BinanceClient
from src.config import settings
from src.data_store import DataStore
from src.market_selector import MarketSelector
from src.notifier import send_notification
from src.scorer import BTC_MARKET, ETH_MARKET, check_market_regime, generate_recommendations
from src.upbit_client import UpbitClient

logger = logging.getLogger(__name__)

_lock = threading.Lock()


class AlreadyRunningError(Exception):
    pass


@dataclass(frozen=True)
class PipelineRunResult:
    run_time: datetime
    regime_bullish: bool
    recommendations: list


def _collect_and_store(data_store: DataStore, upbit_client: UpbitClient, market: str) -> None:
    """BR1 step 2 / Unit 1 business-rules.md BR2/BR3/BR4/BR7: bootstrap-or-incremental per (market,
    timeframe), isolated failure per market (graceful degradation)."""
    for timeframe in ("1h", "4h"):
        try:
            last_time = data_store.get_last_candle_time("upbit", market, timeframe)
            if last_time is None:
                count = max(settings.bootstrap_min_candles, settings.backtest_lookback_days * 24 // (1 if timeframe == "1h" else 4))
                candles = upbit_client.get_ohlcv(market, timeframe, count=count)
            else:
                candles = upbit_client.get_ohlcv(market, timeframe, count=200, to=None)
                candles = [c for c in candles if c.candle_time > last_time]
            data_store.upsert_candles("upbit", market, timeframe, candles)
        except Exception:
            logger.warning("Failed to collect %s %s; skipping this market/timeframe this run", market, timeframe, exc_info=True)


def _collect_and_store_binance(data_store: DataStore, binance_client: BinanceClient, symbol: str) -> None:
    try:
        last_time = data_store.get_last_candle_time("binance", symbol, "4h")
        if last_time is None:
            count = max(settings.bootstrap_min_candles, settings.backtest_lookback_days * 24 // 4)
            candles = binance_client.get_klines(symbol, "4h", limit=count)
        else:
            candles = binance_client.get_klines(symbol, "4h", start_time=last_time, limit=1000)
            candles = [c for c in candles if c.candle_time > last_time]
        data_store.upsert_candles("binance", symbol, "4h", candles)
    except Exception:
        logger.warning("Failed to collect Binance %s; regime check may see stale data this run", symbol, exc_info=True)


def run_recommendation_pipeline(data_store: DataStore | None = None) -> PipelineRunResult:
    """BR1-BR3: the single orchestration entry point shared by POST /run and the scheduler."""
    if not _lock.acquire(blocking=False):
        raise AlreadyRunningError("A pipeline run is already in progress")

    try:
        store = data_store or DataStore(settings.db_path)
        upbit_client = UpbitClient(
            timeout_seconds=settings.http_timeout_seconds,
            max_retries=settings.http_max_retries,
            request_delay_seconds=settings.upbit_request_delay_seconds,
        )
        binance_client = BinanceClient(timeout_seconds=settings.http_timeout_seconds, max_retries=settings.http_max_retries)
        market_selector = MarketSelector(upbit_client, top_n=settings.top_n_candidates)

        now = datetime.now(timezone.utc)

        candidates = market_selector.get_candidate_markets()
        for market in candidates:
            _collect_and_store(store, upbit_client, market)
        _collect_and_store_binance(store, binance_client, BTC_MARKET)
        _collect_and_store_binance(store, binance_client, ETH_MARKET)

        regime_bullish = check_market_regime(store)
        recommendations = generate_recommendations(candidates, store, now)

        store.save_run(now, regime_bullish, recommendations)

        try:
            send_notification(
                recommendations,
                now,
                settings.telegram_bot_token,
                settings.telegram_chat_id,
                settings.discord_webhook_url,
                timeout_seconds=settings.http_timeout_seconds,
            )
        except Exception:
            logger.warning("Notification step failed; pipeline run is still considered successful", exc_info=True)

        return PipelineRunResult(run_time=now, regime_bullish=regime_bullish, recommendations=recommendations)
    finally:
        _lock.release()
