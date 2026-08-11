import logging
import threading
from dataclasses import dataclass
from datetime import datetime, timedelta, timezone

from src.backtest import evaluate_outcome
from src.binance_client import BinanceClient
from src.config import settings
from src.data_store import DataStore
from src.market_selector import BinanceMarketSelector
from src.monitor import check_price_events
from src.notifier import send_notification, send_price_alert
from src.scorer import BTC_MARKET, REGIME_TIMEFRAME, SOURCE, check_market_regime, generate_recommendations

_EVALUATION_WINDOW_HOURS = 24

logger = logging.getLogger(__name__)

_lock = threading.Lock()


class AlreadyRunningError(Exception):
    pass


@dataclass(frozen=True)
class PipelineRunResult:
    run_time: datetime
    regime: str | None
    recommendations: list


def _collect_and_store_binance(
    data_store: DataStore, binance_client: BinanceClient, symbol: str, timeframes: tuple[str, ...] = (REGIME_TIMEFRAME,)
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
            first_time = data_store.get_first_candle_time(SOURCE, symbol, timeframe)
            if first_time is None or first_time > target_start:
                candles = binance_client.get_klines_since(symbol, timeframe, target_start)
            else:
                last_time = data_store.get_last_candle_time(SOURCE, symbol, timeframe)
                candles = binance_client.get_klines(symbol, timeframe, start_time=last_time, limit=1000)
                candles = [c for c in candles if c.candle_time > last_time]
            data_store.upsert_candles(SOURCE, symbol, timeframe, candles)
        except Exception:
            logger.warning("Failed to collect Binance %s %s; skipping this market/timeframe this run", symbol, timeframe, exc_info=True)


def run_price_monitor(data_store: DataStore | None = None) -> list:
    """BR22: 활성 추천의 진입가/매도가/손절가 도달을 확인하고, 새로 발생한 것만 알린다.

    파이프라인 락을 공유하지 않는다 -- 읽기 위주에 짧은 UPDATE만 하고, 시간당 1회 실행되는
    파이프라인이 도는 동안에도 5분 감시는 계속되어야 한다 (SQLite는 WAL 모드).
    """
    store = data_store or DataStore(settings.db_path)
    binance_client = BinanceClient(timeout_seconds=settings.http_timeout_seconds, max_retries=settings.http_max_retries)
    events = check_price_events(store, binance_client, datetime.now(timezone.utc))

    if events:
        try:
            send_price_alert(
                events,
                datetime.now(timezone.utc),
                settings.telegram_bot_token,
                settings.telegram_chat_id,
                settings.discord_webhook_url,
                settings.slack_webhook_url,
                timeout_seconds=settings.http_timeout_seconds,
            )
        except Exception:
            logger.warning("Price alert notification failed; events are already recorded", exc_info=True)
    return events


def evaluate_pending_outcomes(data_store: DataStore, now: datetime) -> None:
    """BR9: for each unevaluated recommendation whose 24h window has closed, judge and persist the
    outcome (Unit 2 BR11/BR12). Isolated per-item failure -- one market's missing/bad data must not
    block the rest."""
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
    """BR1-BR3: the single orchestration entry point shared by POST /run and the scheduler.

    Binance only. Upbit collection and recommendations were removed once recommendations became
    Binance-exclusive -- collecting Upbit candles served nothing else. `UpbitClient` /
    `MarketSelector` are left in place so re-enabling is a small change rather than a rewrite.
    """
    if not _lock.acquire(blocking=False):
        raise AlreadyRunningError("A pipeline run is already in progress")

    try:
        store = data_store or DataStore(settings.db_path)
        binance_client = BinanceClient(timeout_seconds=settings.http_timeout_seconds, max_retries=settings.http_max_retries)
        binance_market_selector = BinanceMarketSelector(binance_client, top_n=settings.top_n_candidates)

        now = datetime.now(timezone.utc)

        candidates = binance_market_selector.get_candidate_markets()
        for symbol in candidates:
            _collect_and_store_binance(store, binance_client, symbol, timeframes=("1h",))
        # BTC 4시간봉은 레짐 판정 전용 (BR20). 후보 코인의 4시간봉은 진입 조건이 1시간봉만
        # 쓰게 되면서 더는 필요하지 않다.
        _collect_and_store_binance(store, binance_client, BTC_MARKET)

        regime = check_market_regime(store)
        recommendations = generate_recommendations(candidates, store)[: settings.recommendations_per_exchange]

        store.save_run(now, regime is not None, recommendations)

        try:
            send_notification(
                recommendations,
                now,
                settings.telegram_bot_token,
                settings.telegram_chat_id,
                settings.discord_webhook_url,
                settings.slack_webhook_url,
                timeout_seconds=settings.http_timeout_seconds,
            )
        except Exception:
            logger.warning("Notification step failed; pipeline run is still considered successful", exc_info=True)

        evaluate_pending_outcomes(store, now)

        return PipelineRunResult(run_time=now, regime=regime, recommendations=recommendations)
    finally:
        _lock.release()
