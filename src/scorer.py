from dataclasses import dataclass
from datetime import datetime

from src.backtest import compute_signal_stats, golden_cross_event
from src.data_store import DataStore
from src.features import as_of, compute_ichimoku, is_bullish

BTC_MARKET = "BTCUSDT"
ETH_MARKET = "ETHUSDT"
BINANCE_TIMEFRAME = "4h"
EXPECTED_RETURN_THRESHOLD = 0.04


@dataclass(frozen=True)
class Recommendation:
    market: str
    expected_return: float
    n: int
    hit_count: int
    source: str = "upbit"


def check_market_regime(data_store: DataStore) -> bool:
    """BR5/BR7-1: BTC AND ETH must both be bullish on their latest closed 4h candle."""
    btc_points = compute_ichimoku(data_store.get_candles("binance", BTC_MARKET, BINANCE_TIMEFRAME))
    eth_points = compute_ichimoku(data_store.get_candles("binance", ETH_MARKET, BINANCE_TIMEFRAME))
    if not btc_points or not eth_points:
        return False
    return is_bullish(btc_points[-1]) and is_bullish(eth_points[-1])


def _composite_signal_on_latest_bar(points_1h, points_4h) -> bool:
    if not points_1h:
        return False
    i = len(points_1h) - 1
    if not golden_cross_event(points_1h, i):
        return False
    trend_point = as_of(points_4h, points_1h[i].candle_time)
    return trend_point is not None and is_bullish(trend_point)


def generate_recommendations(
    candidates: list[str], source: str, data_store: DataStore, now: datetime
) -> list[Recommendation]:
    """BR7/BR13: full live recommendation flow -- regime hard filter, per-candidate signal check,
    backtest lookup, threshold filter. `source` selects which exchange's candles the candidates'
    own signal is computed from ("upbit" | "binance") -- the BTC/ETH regime check itself always
    references Binance regardless of `source` (BR13, single global regime gate)."""
    if not check_market_regime(data_store):
        return []

    btc_points = compute_ichimoku(data_store.get_candles("binance", BTC_MARKET, BINANCE_TIMEFRAME))
    eth_points = compute_ichimoku(data_store.get_candles("binance", ETH_MARKET, BINANCE_TIMEFRAME))

    recommendations = []
    for market in candidates:
        points_1h = compute_ichimoku(data_store.get_candles(source, market, "1h"))
        points_4h = compute_ichimoku(data_store.get_candles(source, market, "4h"))

        if not _composite_signal_on_latest_bar(points_1h, points_4h):
            continue

        stats = compute_signal_stats(market, points_1h, points_4h, btc_points, eth_points, now)
        if stats.expected_return is not None and stats.expected_return >= EXPECTED_RETURN_THRESHOLD:
            recommendations.append(
                Recommendation(
                    market=market, expected_return=stats.expected_return, n=stats.n, hit_count=stats.hit_count, source=source
                )
            )

    return sorted(recommendations, key=lambda r: r.expected_return, reverse=True)
