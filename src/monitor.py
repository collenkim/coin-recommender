import logging
from dataclasses import dataclass
from datetime import datetime, timedelta

from src.backtest import FORWARD_BARS_1H, STOP_LOSS, TARGET_RETURN
from src.tracks import TRACK_BY_KEY
from src.binance_client import BinanceClient
from src.data_store import ENTRY_TOUCHED, STOP_HIT, TARGET_HIT, DataStore, MonitoredRecommendation
from src.scorer import SOURCE

logger = logging.getLogger(__name__)

_MONITOR_TIMEFRAME = "1m"
_MAX_HOLD_HOURS = max([FORWARD_BARS_1H] + [t.hold_hours for t in TRACK_BY_KEY.values()])


def _rules(rec) -> tuple[float, float, int]:
    """BR25: 트랙마다 목표·손절·보유기간이 다르다. 하나의 상수를 공유하면 장기 추천이 단기
    기준으로 잘못 알림되고, 아직 살아 있는 포지션이 종료 처리된다.

    기존 레짐 게이트 트랙(BR18~BR21)은 track='regime'으로 저장된다 -- BR25 '단기'와 목표·손절이
    같지만 보유가 24시간 vs 12시간이라 키를 나눴다. BR25 스펙에 없는 키는 기존 규칙으로 떨어지며,
    이 배포 이전에 저장된 track='short' 행도 그 경로를 타야 하므로 기본값을 'regime'으로 둔다."""
    spec = TRACK_BY_KEY.get(getattr(rec, "track", "regime"))
    if spec is not None:
        return spec.target, spec.stop, spec.hold_hours
    return TARGET_RETURN, STOP_LOSS, FORWARD_BARS_1H


@dataclass(frozen=True)
class PriceEvent:
    market: str
    run_time: datetime
    kind: str  # ENTRY_TOUCHED | TARGET_HIT | STOP_HIT
    price: float
    at: datetime
    track: str = "regime"


def _events_for(rec: MonitoredRecommendation, candles: list) -> list[PriceEvent]:
    """BR22: 1분봉을 시간순으로 훑으며 최초 도달 시점을 찾는다.

    5분 간격 시점 가격만 보면 그 사이에 스쳐간 도달을 놓친다. 백테스트가 고가/저가로 터치를
    판정하는 것과 같은 기준을 쓰려면 봉의 고가/저가를 봐야 한다.

    한 봉에서 목표가와 손절가를 동시에 만족하면 `simulate_trade`와 동일하게 손절을 먼저
    체결된 것으로 본다. 그리고 둘 중 하나가 나오면 포지션이 끝난 것이므로 즉시 중단한다.
    """
    target, stop, _ = _rules(rec)
    track = getattr(rec, "track", "regime")
    target_price = rec.entry_price * (1 + target)
    stop_price = rec.entry_price * (1 - stop)
    entry_seen = rec.entry_touched_at is not None
    events: list[PriceEvent] = []

    for candle in candles:
        if candle.candle_time < rec.entry_time:
            continue
        if candle.low <= stop_price:
            events.append(PriceEvent(rec.market, rec.run_time, STOP_HIT, stop_price, candle.candle_time, track))
            break
        if candle.high >= target_price:
            events.append(PriceEvent(rec.market, rec.run_time, TARGET_HIT, target_price, candle.candle_time, track))
            break
        if not entry_seen and candle.low <= rec.entry_price:
            entry_seen = True
            events.append(PriceEvent(rec.market, rec.run_time, ENTRY_TOUCHED, rec.entry_price, candle.candle_time, track))

    return events


def check_price_events(data_store: DataStore, binance_client: BinanceClient, now: datetime) -> list[PriceEvent]:
    """BR22: 활성 추천마다 진입가/매도가/손절가 도달을 확인하고, 새로 발생한 이벤트만 돌려준다.

    이미 기록된 이벤트는 다시 알리지 않는다(`mark_price_event`가 NULL일 때만 쓰므로 기록 자체가
    중복 방지 장치다). 한 종목의 조회 실패가 나머지 감시를 막지 않는다 -- Unit 1 BR7과 같은 방향.
    """
    # BR25: 조회는 가장 긴 트랙 기준으로 넓게 하고, 보유 기간은 **트랙별로** 판정한다.
    # 하나의 창을 공유하면 24시간으로는 장기 포지션이 하루 만에 감시에서 빠지고, 7일로는
    # 이미 끝난 초단기 추천을 계속 조회한다.
    since = now - timedelta(hours=_MAX_HOLD_HOURS)
    new_events: list[PriceEvent] = []

    for rec in data_store.get_monitorable_recommendations(since):
        if rec.run_time < now - timedelta(hours=_rules(rec)[2]):
            continue
        try:
            candles = binance_client.get_klines_since(rec.market, _MONITOR_TIMEFRAME, rec.entry_time, max_requests=3)
        except Exception:
            logger.warning("Failed to fetch 1m candles for %s; skipping this check", rec.market, exc_info=True)
            continue

        for event in _events_for(rec, candles):
            data_store.mark_price_event(event.run_time, event.market, event.kind, event.at, event.track)
            new_events.append(event)

    return new_events
