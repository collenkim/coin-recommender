from dataclasses import dataclass
from datetime import datetime

from src.backtest import (
    MIN_HIT_RATE,
    MIN_SIGNAL_SAMPLES,
    build_regime_series,
    compute_signal_stats,
    entry_signal,
)
from src.data_store import DataStore, close_time
from src.features import compute_ichimoku

SOURCE = "binance"
BTC_MARKET = "BTCUSDT"
REGIME_TIMEFRAME = "4h"


@dataclass(frozen=True)
class Recommendation:
    market: str
    n: int
    hit_count: int
    hit_rate: float
    hit_rate_lower: float
    expected_return: float
    source: str = SOURCE
    entry_time: datetime | None = None
    entry_price: float | None = None
    max_drawdown: float | None = None


def _regime_series(data_store: DataStore) -> list[tuple[datetime, str | None]]:
    return build_regime_series(data_store.get_candles(SOURCE, BTC_MARKET, REGIME_TIMEFRAME))


def check_market_regime(data_store: DataStore) -> str | None:
    """BR20: 지금이 강한 상승장인지 반등 상승장인지, 둘 다 아니면 None.

    BTC 4시간봉 수집이 실패해 이력이 없으면 None -- 레짐을 알 수 없을 때 진입하지 않는 쪽이
    안전하다 (Unit 1 BR7의 graceful degradation과 같은 방향)."""
    series = _regime_series(data_store)
    return series[-1][1] if series else None


def generate_recommendations(candidates: list[str], data_store: DataStore) -> list[Recommendation]:
    """BR13/BR21: 레짐 게이트 -> 후보별 진입 조건 -> 자기 이력 기준 확률 하한 순으로 거른다.

    정렬 기준이 적중률 자체가 아니라 95% 신뢰 하한인 이유는, 표본 3건에 3승인 코인이
    적중률 100%로 목록 맨 위에 오는 것을 막기 위해서다."""
    regime_series = _regime_series(data_store)
    if not regime_series or regime_series[-1][1] is None:
        return []

    recommendations = []
    for market in candidates:
        candles_1h = data_store.get_candles(SOURCE, market, "1h")
        points_1h = compute_ichimoku(candles_1h)
        if not points_1h or not entry_signal(candles_1h, points_1h, len(points_1h) - 1):
            continue

        stats = compute_signal_stats(market, candles_1h, points_1h, regime_series)
        if stats.n < MIN_SIGNAL_SAMPLES or stats.hit_rate is None or stats.hit_rate < MIN_HIT_RATE:
            continue

        entry_candle = candles_1h[-1]
        recommendations.append(
            Recommendation(
                market=market,
                n=stats.n,
                hit_count=stats.hit_count,
                hit_rate=stats.hit_rate,
                hit_rate_lower=stats.hit_rate_lower,
                expected_return=stats.expected_return,
                entry_time=close_time(entry_candle),
                entry_price=entry_candle.close,
                max_drawdown=stats.max_drawdown,
            )
        )

    return sorted(recommendations, key=lambda r: r.hit_rate_lower, reverse=True)
