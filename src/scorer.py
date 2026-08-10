from dataclasses import dataclass
from datetime import datetime

from src.backtest import FORWARD_BARS_1H, MIN_SIGNAL_SAMPLES, compute_signal_stats, golden_cross_within
from src.data_store import DataStore, close_time
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
    # BR16 entry guide -- entry_time/entry_price are the exact bar the backtest measures from, so the
    # published entry matches the trade expected_return describes.
    entry_time: datetime | None = None
    entry_price: float | None = None
    max_drawdown: float | None = None


def check_market_regime(data_store: DataStore) -> bool:
    """BR5/BR7-1: BTC AND ETH must both be bullish on their latest closed 4h candle."""
    btc_points = compute_ichimoku(data_store.get_candles("binance", BTC_MARKET, BINANCE_TIMEFRAME))
    eth_points = compute_ichimoku(data_store.get_candles("binance", ETH_MARKET, BINANCE_TIMEFRAME))
    if not btc_points or not eth_points:
        return False
    return is_bullish(btc_points[-1]) and is_bullish(eth_points[-1])


def _composite_signal_on_latest_bar(points_1h, points_4h) -> bool:
    """BR7 step 2: same entry test the backtest samples use (backtest._composite_signal), applied to
    the latest bar -- a golden cross within the last GOLDEN_CROSS_LOOKBACK_BARS bars (BR4) plus the
    4h trend filter as-of now. Both sides must stay in step or expected_return would describe a
    different entry than the one being recommended."""
    if not points_1h:
        return False
    i = len(points_1h) - 1
    if not golden_cross_within(points_1h, i):
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
        candles_1h = data_store.get_candles(source, market, "1h")
        points_1h = compute_ichimoku(candles_1h)
        points_4h = compute_ichimoku(data_store.get_candles(source, market, "4h"))

        if not _composite_signal_on_latest_bar(points_1h, points_4h):
            continue

        stats = compute_signal_stats(market, points_1h, points_4h, btc_points, eth_points, now, candles_1h=candles_1h)
        # BR15: `n` is now a count of distinct past crossovers, so this is a real evidence floor --
        # it drops coins like KRW-WLD whose "100% hit rate" was a single observation.
        if (
            stats.expected_return is not None
            and stats.expected_return >= EXPECTED_RETURN_THRESHOLD
            and stats.n >= MIN_SIGNAL_SAMPLES
        ):
            entry_candle = candles_1h[-1] if candles_1h else None
            recommendations.append(
                Recommendation(
                    market=market,
                    expected_return=stats.expected_return,
                    n=stats.n,
                    hit_count=stats.hit_count,
                    source=source,
                    entry_time=close_time(entry_candle) if entry_candle else None,
                    entry_price=entry_candle.close if entry_candle else None,
                    max_drawdown=stats.max_drawdown,
                )
            )

    return sorted(recommendations, key=lambda r: r.expected_return, reverse=True)
