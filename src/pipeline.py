import logging
import threading
from dataclasses import dataclass
from datetime import datetime, timedelta, timezone

from src.backtest import evaluate_outcome
from src.binance_client import BinanceClient
from src.config import settings
from src.data_store import TIMEFRAME_HOURS, DataStore
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


def _bars_between(timeframe: str, start: datetime, end: datetime) -> int:
    """Candle count covering [start, end] on `timeframe`, floored at bootstrap_min_candles so a
    market with almost no gap still gets a usable minimum of history."""
    span_bars = int((end - start).total_seconds() // 3600 // TIMEFRAME_HOURS[timeframe]) + 1
    return max(settings.bootstrap_min_candles, span_bars)


def _collect_and_store(data_store: DataStore, upbit_client: UpbitClient, market: str) -> None:
    """BR1 step 2 / Unit 1 business-rules.md BR2/BR3/BR4/BR7: bootstrap-or-incremental per (market,
    timeframe), isolated failure per market (graceful degradation).

    The backfill leg mirrors _collect_and_store_binance (BR9) and exists for the same reason:
    the incremental path only ever moves forward, so a market bootstrapped under a shorter
    `backtest_lookback_days` would keep its old depth forever and a raised lookback would silently
    apply to Binance only.

    Unlike Binance, the backfill asks for the *missing older span only* (`to=first_time`) instead of
    re-fetching the whole window. Upbit pages 200 candles at a time (Binance does 1000), and a coin
    listed after `target_start` can never satisfy `first <= target_start`, so it takes this branch on
    every run -- fetching only the gap keeps that permanent cost at one request instead of dozens.
    """
    now = datetime.now(timezone.utc)
    target_start = now - timedelta(days=settings.backtest_lookback_days)
    for timeframe in ("1h", "4h"):
        try:
            first_time = data_store.get_first_candle_time("upbit", market, timeframe)
            if first_time is None:
                candles = upbit_client.get_ohlcv(market, timeframe, count=_bars_between(timeframe, target_start, now))
            else:
                last_time = data_store.get_last_candle_time("upbit", market, timeframe)
                candles = upbit_client.get_ohlcv(market, timeframe, count=200, to=None)
                candles = [c for c in candles if c.candle_time > last_time]
                if first_time > target_start:
                    candles += upbit_client.get_ohlcv(
                        market, timeframe, count=_bars_between(timeframe, target_start, first_time), to=first_time
                    )
            data_store.upsert_candles("upbit", market, timeframe, candles)
        except Exception:
            logger.warning("Failed to collect %s %s; skipping this market/timeframe this run", market, timeframe, exc_info=True)


def _collect_and_store_binance(
    data_store: DataStore, binance_client: BinanceClient, symbol: str, timeframes: tuple[str, ...] = ("4h",)
) -> None:
    """BR9 (data-pipeline): backfill-or-incremental Binance collection, per-timeframe failure isolated.

    Backfill exists because the plain incremental path can only ever move forward: markets stored
    before pagination was added hold ~1000 candles and would never reach back to the configured
    lookback on their own. Once history is deep enough this branch stops firing and each run costs
    a single request per timeframe.

    Known cost (accepted): a coin listed more recently than the lookback window can never satisfy
    `first <= target_start`, so it re-fetches its (short) history each run. That is a handful of
    extra requests per hour, well inside Binance's public rate limit.
    """
    target_start = datetime.now(timezone.utc) - timedelta(days=settings.backtest_lookback_days)
    for timeframe in timeframes:
        try:
            first_time = data_store.get_first_candle_time("binance", symbol, timeframe)
            if first_time is None or first_time > target_start:
                candles = binance_client.get_klines_since(symbol, timeframe, target_start)
            else:
                last_time = data_store.get_last_candle_time("binance", symbol, timeframe)
                candles = binance_client.get_klines(symbol, timeframe, start_time=last_time, limit=1000)
                candles = [c for c in candles if c.candle_time > last_time]
            data_store.upsert_candles("binance", symbol, timeframe, candles)
        except Exception:
            logger.warning("Failed to collect Binance %s %s; skipping this market/timeframe this run", symbol, timeframe, exc_info=True)


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
            _collect_and_store_binance(store, binance_client, symbol, timeframes=("1h", "4h"))
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
