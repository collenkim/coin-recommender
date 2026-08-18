import logging
from dataclasses import dataclass
from datetime import datetime, timedelta

from src.backtest import FORWARD_BARS_1H, STOP_LOSS, TARGET_RETURN
from src.long_track import LONG_HOLD_BARS_4H, LONG_STOP_LOSS, LONG_TARGET_RETURN
from src.binance_client import BinanceClient
from src.data_store import ENTRY_TOUCHED, STOP_HIT, TARGET_HIT, DataStore, MonitoredRecommendation
from src.scorer import SOURCE

logger = logging.getLogger(__name__)

_MONITOR_TIMEFRAME = "1m"
_LONG_HOLD_HOURS = LONG_HOLD_BARS_4H * 4


def _hold_hours(rec) -> int:
    """BR24: 추천이 살아 있는 기간. 단기 24시간, 장기 90일."""
    return _LONG_HOLD_HOURS if getattr(rec, "track", "short") == "long" else FORWARD_BARS_1H


@dataclass(frozen=True)
class PriceEvent:
    market: str
    run_time: datetime
    kind: str  # ENTRY_TOUCHED | TARGET_HIT | STOP_HIT
    price: float
    at: datetime


def _events_for(rec: MonitoredRecommendation, candles: list) -> list[PriceEvent]:
    """BR22: 1분봉을 시간순으로 훑으며 최초 도달 시점을 찾는다.

    5분 간격 시점 가격만 보면 그 사이에 스쳐간 도달을 놓친다. 백테스트가 고가/저가로 터치를
    판정하는 것과 같은 기준을 쓰려면 봉의 고가/저가를 봐야 한다.

    한 봉에서 목표가와 손절가를 동시에 만족하면 `simulate_trade`와 동일하게 손절을 먼저
    체결된 것으로 본다. 그리고 둘 중 하나가 나오면 포지션이 끝난 것이므로 즉시 중단한다.
    """
    # BR24: 트랙마다 목표·손절이 다르다. 단기 상수를 공유하면 장기 추천이 +3%/-2%에서
    # 잘못 알림되고, 실제로는 아직 살아 있는 포지션이 종료 처리된다.
    if getattr(rec, "track", "short") == "long":
        target_price = rec.entry_price * (1 + LONG_TARGET_RETURN)
        stop_price = rec.entry_price * (1 - LONG_STOP_LOSS)
    else:
        target_price = rec.entry_price * (1 + TARGET_RETURN)
        stop_price = rec.entry_price * (1 - STOP_LOSS)
    entry_seen = rec.entry_touched_at is not None
    events: list[PriceEvent] = []

    for candle in candles:
        if candle.candle_time < rec.entry_time:
            continue
        if candle.low <= stop_price:
            events.append(PriceEvent(rec.market, rec.run_time, STOP_HIT, stop_price, candle.candle_time))
            break
        if candle.high >= target_price:
            events.append(PriceEvent(rec.market, rec.run_time, TARGET_HIT, target_price, candle.candle_time))
            break
        if not entry_seen and candle.low <= rec.entry_price:
            entry_seen = True
            events.append(PriceEvent(rec.market, rec.run_time, ENTRY_TOUCHED, rec.entry_price, candle.candle_time))

    return events


def check_price_events(data_store: DataStore, binance_client: BinanceClient, now: datetime) -> list[PriceEvent]:
    """BR22: 활성 추천마다 진입가/매도가/손절가 도달을 확인하고, 새로 발생한 이벤트만 돌려준다.

    이미 기록된 이벤트는 다시 알리지 않는다(`mark_price_event`가 NULL일 때만 쓰므로 기록 자체가
    중복 방지 장치다). 한 종목의 조회 실패가 나머지 감시를 막지 않는다 -- Unit 1 BR7과 같은 방향.
    """
    # BR24: 조회는 넓게(장기 90일) 하고 보유 기간은 **트랙별로** 판정한다. 하나의 창을 공유하면
    # 24시간으로는 장기 포지션이 하루 만에 감시에서 빠지고, 90일로는 이미 끝난 단기 추천을 계속
    # 조회한다.
    since = now - timedelta(hours=max(FORWARD_BARS_1H, _LONG_HOLD_HOURS))
    new_events: list[PriceEvent] = []

    for rec in data_store.get_monitorable_recommendations(since):
        if rec.run_time < now - timedelta(hours=_hold_hours(rec)):
            continue
        try:
            candles = binance_client.get_klines_since(rec.market, _MONITOR_TIMEFRAME, rec.entry_time, max_requests=3)
        except Exception:
            logger.warning("Failed to fetch 1m candles for %s; skipping this check", rec.market, exc_info=True)
            continue

        for event in _events_for(rec, candles):
            data_store.mark_price_event(event.run_time, event.market, event.kind, event.at)
            new_events.append(event)

    return new_events
