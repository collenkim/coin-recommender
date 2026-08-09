import logging
import threading
from dataclasses import dataclass
from datetime import datetime, timedelta, timezone

from src.backtest import evaluate_outcome
from src.binance_client import BinanceClient
from src.config import settings
from src.data_store import DataStore
from src.market_selector import BinanceMarketSelector, MarketSelector
from src.notifier import send_notification
from src.scorer import BTC_MARKET, ETH_MARKET, check_market_regime, generate_recommendations
from src.upbit_client import UpbitClient

_EVALUATION_WINDOW_HOURS = 24

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


def _collect_and_store_binance_candidate(data_store: DataStore, binance_client: BinanceClient, symbol: str) -> None:
    """BR9 (data-pipeline): 1h+4h collection for a Binance recommendation candidate, mirroring
    _collect_and_store's bootstrap-or-incremental + per-market failure isolation for Upbit."""
    for interval in ("1h", "4h"):
        try:
            last_time = data_store.get_last_candle_time("binance", symbol, interval)
            if last_time is None:
                count = max(
                    settings.bootstrap_min_candles,
                    settings.backtest_lookback_days * 24 // (1 if interval == "1h" else 4),
                )
                candles = binance_client.get_klines(symbol, interval, limit=count)
            else:
                candles = binance_client.get_klines(symbol, interval, start_time=last_time, limit=1000)
                candles = [c for c in candles if c.candle_time > last_time]
            data_store.upsert_candles("binance", symbol, interval, candles)
        except Exception:
            logger.warning("Failed to collect Binance %s %s; skipping this market/timeframe this run", symbol, interval, exc_info=True)


def evaluate_pending_outcomes(data_store: DataStore, now: datetime) -> None:
    """BR9: for each unevaluated recommendation whose 24h window has closed, judge and persist the
    outcome (Unit 2 BR11/BR12). Isolated per-item failure, mirrors _collect_and_store's graceful
    degradation (BR7) -- one market's missing/bad data must not block the rest."""
    cutoff = now - timedelta(hours=_EVALUATION_WINDOW_HOURS)
    for market, run_time, source in data_store.get_pending_evaluations(older_than=cutoff):
        try:
            candles_1h = data_store.get_candles(source, market, "1h")
            outcome = evaluate_outcome(market, run_time, candles_1h, now)
            if outcome is not None:
                data_store.record_outcome(outcome)
        except Exception:
            logger.warning("Failed to evaluate outcome for %s %s; will retry next run", market, run_time, exc_info=True)


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
        binance_market_selector = BinanceMarketSelector(binance_client, top_n=settings.top_n_candidates)

        now = datetime.now(timezone.utc)

        candidates = market_selector.get_candidate_markets()
        binance_candidates = binance_market_selector.get_candidate_markets()
        for market in candidates:
            _collect_and_store(store, upbit_client, market)
        for symbol in binance_candidates:
            _collect_and_store_binance_candidate(store, binance_client, symbol)
        _collect_and_store_binance(store, binance_client, BTC_MARKET)
        _collect_and_store_binance(store, binance_client, ETH_MARKET)

        regime_bullish = check_market_regime(store)
        per_exchange = settings.recommendations_per_exchange
        upbit_recommendations = generate_recommendations(candidates, "upbit", store, now)[:per_exchange]
        binance_recommendations = generate_recommendations(binance_candidates, "binance", store, now)[:per_exchange]
        recommendations = upbit_recommendations + binance_recommendations

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

        evaluate_pending_outcomes(store, now)

        return PipelineRunResult(run_time=now, regime_bullish=regime_bullish, recommendations=recommendations)
    finally:
        _lock.release()
