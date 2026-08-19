import logging
import threading
from dataclasses import dataclass
from datetime import datetime, timedelta, timezone

from src.backtest import REGIME_WARMUP_DAYS, evaluate_outcome
from src.binance_client import BinanceClient
from src.config import settings
from src.data_store import TIMEFRAME_HOURS, DataStore
from src.market_selector import BinanceMarketSelector
from src.monitor import check_price_events
from src.notifier import send_notification, send_price_alert
from src.premium import fetch_btc_premium, is_reverse
from src.scorer import (
    PHASE_MARKETS,
    REGIME_TIMEFRAME,
    SOURCE,
    check_market_phase,
    check_market_regime,
    generate_all_tracks,
    generate_recommendations,
)
from src.tracks import COLLECTED_TIMEFRAMES, TRACKS

_EVALUATION_WINDOW_HOURS = 24
# BR31: 중복 알림 억제 조회 범위. 가장 긴 트랙 보유(7일)보다 넉넉해야 같은 진입봉이 다시 알려지지 않는다.
_ANNOUNCE_MEMORY_DAYS = 10
# BR35: 역프 상태를 기억하는 키. 조건이 유지되는 동안 반복 알리지 않고 **진입할 때 한 번**만 알린다.
_REVERSE_PREMIUM_STATE = "reverse_premium_active"

logger = logging.getLogger(__name__)

_lock = threading.Lock()


class AlreadyRunningError(Exception):
    pass


@dataclass(frozen=True)
class PipelineRunResult:
    run_time: datetime
    regime: str | None
    recommendations: list          # BR18~BR21 기존 단기 트랙 (레짐 게이트)
    phase: object | None = None    # BR23 MarketPhase
    tracks: dict | None = None     # BR25 4트랙 {key: [Recommendation]}


_EXCHANGE_EPOCH = datetime(2017, 1, 1, tzinfo=timezone.utc)  # 바이낸스 개장(2017-07)보다 이르면 충분


def _is_exchange_earliest(
    data_store: DataStore,
    binance_client: BinanceClient,
    symbol: str,
    timeframe: str,
    first_time: datetime,
) -> bool:
    """보유 중인 최초봉이 거래소가 줄 수 있는 최초봉인가 (= 더 받을 과거가 없는가).

    BR28: 거래소 최초봉은 **한 번 확인하면 바뀌지 않는 값**이므로 DB에 캐시한다. 캐시가 없을 때만
    1요청을 쓴다 -- 30종 x 7봉이면 매 실행 210요청을 아낀다(시간당 424 -> 214).

    실패하면 False를 돌려 기존 백필 경로로 떨어진다 -- 이 판단이 틀려서 수집을 건너뛰는 것보다
    한 번 더 받는 쪽이 안전하다."""
    cached = data_store.get_exchange_earliest(SOURCE, symbol, timeframe)
    if cached is not None:
        return cached >= first_time
    try:
        earliest = binance_client.get_klines(symbol, timeframe, start_time=_EXCHANGE_EPOCH, limit=1)
    except Exception:
        logger.warning("Failed to probe earliest candle for %s %s; falling back to backfill", symbol, timeframe, exc_info=True)
        return False
    if not earliest:
        return False
    data_store.set_exchange_earliest(SOURCE, symbol, timeframe, earliest[0].candle_time, datetime.now(timezone.utc))
    return earliest[0].candle_time >= first_time


def _is_up_to_date(data_store: DataStore, symbol: str, timeframe: str) -> bool:
    """BR29: 마지막 저장 봉 다음 봉이 아직 마감되지 않았으면 True (조회 불필요).

    `close_time`이 봉의 마감 시각을 주므로, 마지막 저장 봉의 **다음** 봉이 마감될 시각을 계산해
    지금과 비교한다. 이력이 없으면 False -- 받아야 한다."""
    last = data_store.get_last_candle_time(SOURCE, symbol, timeframe)
    if last is None:
        return False
    interval = timedelta(hours=TIMEFRAME_HOURS[timeframe])
    next_close = last + interval * 2  # 마지막 봉의 다음 봉이 마감되는 시각
    return datetime.now(timezone.utc) < next_close


def _collect_and_store_binance(
    data_store: DataStore,
    binance_client: BinanceClient,
    symbol: str,
    timeframes: tuple[str, ...] = (REGIME_TIMEFRAME,),
    lookback_days: int | None = None,
) -> None:
    """BR9 (data-pipeline): backfill-or-incremental Binance collection, per-timeframe failure isolated.

    Backfill exists because the plain incremental path can only ever move forward: markets stored
    before pagination was added hold ~1000 candles and would never reach back to the configured
    lookback on their own. Once history is deep enough this branch stops firing and each run costs
    a single request per timeframe.

    `first <= target_start`를 그대로 쓰면 **거래소에 없는 과거를 영원히 다시 받는다**. lookback이
    5년이던 시절엔 최근 상장 코인만 걸려 무시할 만했지만(원 주석의 "accepted cost"), 12년으로
    늘린 뒤에는 바이낸스 자체가 2017-07 시작이라 **모든 종목이 매 실행마다 전량 재수집** 대상이
    된다 -- 실측 시간당 약 600요청/136초. 그래서 "거래소가 줄 수 있는 가장 오래된 봉을 이미
    갖고 있는가"를 함께 본다(종목·타임프레임당 1요청). 있으면 더 받을 과거가 없으므로 증분으로
    간다. 2026-08-18 lookback 확대로 드러난 결함이다.
    """
    target_start = datetime.now(timezone.utc) - timedelta(days=lookback_days or settings.backtest_lookback_days)
    for timeframe in timeframes:
        # BR29: 아직 새 봉이 마감되지 않았으면 조회 자체를 건너뛴다. 주봉은 주 1회, 월봉은 월 1회만
        # 새 봉이 생기는데 매시간 물어보고 있었다 -- 30종 x 7봉이면 시간당 210요청 중 상당수가
        # "변화 없음"을 확인하는 데만 쓰였다.
        if _is_up_to_date(data_store, symbol, timeframe):
            continue
        try:
            first_time = data_store.get_first_candle_time(SOURCE, symbol, timeframe)
            if first_time is not None and first_time > target_start and _is_exchange_earliest(
                data_store, binance_client, symbol, timeframe, first_time
            ):
                # 거래소의 첫 봉을 이미 보유 -- target_start까지 못 미쳐도 그건 상장 전이라 없는 것이다.
                first_time = target_start
            if first_time is None or first_time > target_start:
                candles = binance_client.get_klines_since(symbol, timeframe, target_start)
            else:
                # BR30: 증분도 페이지네이션한다. `get_klines`는 1회 1,000봉이 상한이라 15분봉이면
                # 10일치뿐이다 -- 오래 뒤처진 타임프레임은 따라잡는 데 수백 회가 걸리고, 그동안
                # 데이터에 구멍이 남는다(실측: BNB 15분봉이 2022-05에서 멈춰 있었다).
                # `get_klines_since`는 최신이면 짧은 페이지를 만나 1요청으로 끝나므로 정상
                # 상태의 비용은 같다.
                last_time = data_store.get_last_candle_time(SOURCE, symbol, timeframe)
                candles = binance_client.get_klines_since(symbol, timeframe, last_time)
                candles = [c for c in candles if c.candle_time > last_time]
            data_store.upsert_candles(SOURCE, symbol, timeframe, candles)
        except Exception:
            logger.warning("Failed to collect Binance %s %s; skipping this market/timeframe this run", symbol, timeframe, exc_info=True)


def _reverse_premium_to_report(data_store: DataStore, now: datetime):
    """BR35: 역프가 **새로 시작됐을 때만** 돌려준다. 조건이 유지되는 동안에는 None.

    30분마다 도는데 역프는 몇 시간씩 이어질 수 있어, 상태 전환으로 걸지 않으면 같은 이벤트를
    수십 번 알리게 된다."""
    premium = fetch_btc_premium()
    active = is_reverse(premium)
    was_active = data_store.get_state(_REVERSE_PREMIUM_STATE) == "1"
    data_store.set_state(_REVERSE_PREMIUM_STATE, "1" if active else "0", now)
    return premium if (active and not was_active) else None


def _drop_already_announced(recommendations: list, announced: set) -> list:
    """이미 알린 (종목, 트랙, 진입봉) 조합을 제거한다."""
    result = []
    for r in recommendations:
        entry_time = getattr(r, "entry_time", None)
        key = (r.market, getattr(r, "track", "regime"), entry_time.isoformat() if entry_time else None)
        if key in announced:
            continue
        result.append(r)
    return result


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
        # BR33: 상장일 캐시를 쓰도록 store를 넘긴다 -- 안 넘기면 매 실행 후보마다 1요청이 더 나간다.
        binance_market_selector = BinanceMarketSelector(
            binance_client, top_n=settings.top_n_candidates, data_store=store
        )

        now = datetime.now(timezone.utc)

        candidates = binance_market_selector.get_candidate_markets()
        # BR25: 4트랙이 쓰는 타임프레임을 상위 후보에 한해 모은다. 1m/3m/5m은 제외했다 --
        # 20종 9년 기준 23GB인데 초단기 기여가 창마다 부호가 갈렸다.
        track_candidates = candidates[: settings.long_top_n_candidates]
        for symbol in candidates:
            timeframes = COLLECTED_TIMEFRAMES if symbol in track_candidates else ("1h",)
            _collect_and_store_binance(store, binance_client, symbol, timeframes=timeframes)
        # BTC 4시간봉은 레짐 판정 전용 (BR20). 200일 이동평균 워밍업분을 더 깊게 받는다 -- 그만큼이
        # 없으면 백테스트 앞구간에서 반등 판정이 불가능해져 표본이 잘린다.
        # ETH 4시간봉은 BR23 문구 판정 전용이다 -- 추천 후보에는 여전히 들어가지 않는다(BR8).
        for symbol in PHASE_MARKETS:
            _collect_and_store_binance(
                store,
                binance_client,
                symbol,
                lookback_days=settings.backtest_lookback_days + REGIME_WARMUP_DAYS,
            )

        regime = check_market_regime(store)
        phase = check_market_phase(store)
        premium = _reverse_premium_to_report(store, now)
        recommendations = generate_recommendations(candidates, store)[: settings.recommendations_per_exchange]
        tracks = generate_all_tracks(track_candidates, store, phase, settings.recommendations_per_exchange)

        # BR31: 같은 진입봉을 이미 알렸으면 다시 알리지 않는다. 진입 신호는 4시간봉 하나를
        # 가리키는데 파이프라인은 30분마다 돌므로, 억제가 없으면 같은 추천이 8회 발송된다.
        # 저장은 그대로 하되(회차 기록은 남아야 한다) 알림에서만 걸러낸다.
        announced = store.get_announced_entries(now - timedelta(days=_ANNOUNCE_MEMORY_DAYS))
        fresh_recommendations = _drop_already_announced(recommendations, announced)
        fresh_tracks = {key: _drop_already_announced(items, announced) for key, items in tracks.items()}

        # BR37: **알린 것만 저장한다.** 이전에는 중복도 저장해 같은 4시간봉 진입이 30분마다
        # 쌓였고(실측 원시 118행 = 고유 진입 17건), 실적 집계가 7배 부풀 뻔했다. 회차 기록은
        # `pipeline_runs`가 담당하므로 중복 행은 아무것도 더해주지 않는다.
        store.save_run(now, regime is not None, fresh_recommendations + [r for v in fresh_tracks.values() for r in v])

        try:
            send_notification(
                fresh_recommendations,
                now,
                settings.telegram_bot_token,
                settings.telegram_chat_id,
                settings.discord_webhook_url,
                settings.slack_webhook_url,
                timeout_seconds=settings.http_timeout_seconds,
                phase=phase,
                tracks=fresh_tracks,
                now=now,
                premium=premium,
                performance=store.get_live_performance(),
            )
        except Exception:
            logger.warning("Notification step failed; pipeline run is still considered successful", exc_info=True)

        evaluate_pending_outcomes(store, now)

        return PipelineRunResult(
            run_time=now,
            regime=regime,
            recommendations=recommendations,
            phase=phase,
            tracks=tracks,
        )
    finally:
        _lock.release()
