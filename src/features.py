import math
from dataclasses import dataclass
from datetime import datetime

import pandas as pd
import pandas_ta as ta

from src.data_store import Candle


@dataclass(frozen=True)
class IchimokuPoint:
    candle_time: datetime
    close: float
    tenkan: float | None
    kijun: float | None
    senkou_a: float | None
    senkou_b: float | None


def _nan_to_none(value: float) -> float | None:
    return None if value is None or math.isnan(value) else float(value)


def compute_ichimoku(candles: list[Candle], tenkan: int = 9, kijun: int = 26, senkou: int = 52) -> list[IchimokuPoint]:
    """Wraps pandas-ta's ichimoku(). Empirically verified (2026-08, pandas-ta 0.4.71b0): the returned
    ISA_9/ISB_26 columns are already aligned to each bar's own applicable cloud value (shifted by
    `kijun - 1` periods internally) with no future projection -- used as-is, no extra shifting
    (see business-rules.md BR1)."""
    if not candles:
        return []

    df = pd.DataFrame(
        {
            "high": [c.high for c in candles],
            "low": [c.low for c in candles],
            "close": [c.close for c in candles],
        }
    )

    result, _ = ta.ichimoku(df["high"], df["low"], df["close"], tenkan=tenkan, kijun=kijun, senkou=senkou)

    if result is None:
        # pandas-ta returns (None, None) when there isn't enough data for any indicator to be computed
        return [
            IchimokuPoint(candle_time=c.candle_time, close=c.close, tenkan=None, kijun=None, senkou_a=None, senkou_b=None)
            for c in candles
        ]

    tenkan_col = f"ITS_{tenkan}"
    kijun_col = f"IKS_{kijun}"
    senkou_a_col = f"ISA_{tenkan}"
    senkou_b_col = f"ISB_{kijun}"

    return [
        IchimokuPoint(
            candle_time=candles[i].candle_time,
            close=candles[i].close,
            tenkan=_nan_to_none(result[tenkan_col].iloc[i]),
            kijun=_nan_to_none(result[kijun_col].iloc[i]),
            senkou_a=_nan_to_none(result[senkou_a_col].iloc[i]),
            senkou_b=_nan_to_none(result[senkou_b_col].iloc[i]),
        )
        for i in range(len(candles))
    ]


def compute_rsi(candles: list[Candle], length: int = 14) -> list[float | None]:
    """BR26: 각 봉의 RSI(14). 워밍업 구간은 None.

    보조지표 중 RSI를 채택한 이유는 실측이다 -- ADX는 오히려 기대수익을 낮췄고(초단기 -0.05%p),
    기준선 상승·양운도 중립~음수였다."""
    if not candles:
        return []
    values = ta.rsi(pd.Series([c.close for c in candles]), length=length)
    if values is None:
        return [None] * len(candles)
    return [_nan_to_none(v) for v in values.tolist()]


def above_cloud(point: IchimokuPoint) -> bool:
    """종가가 구름 위인가. 워밍업 구간은 False."""
    if point.senkou_a is None or point.senkou_b is None:
        return False
    return point.close > max(point.senkou_a, point.senkou_b)


def is_bullish(point: IchimokuPoint) -> bool:
    """BR2: above cloud AND bullish (span A > span B). False during warmup (None values)."""
    if point.senkou_a is None or point.senkou_b is None:
        return False
    above_cloud = point.close > max(point.senkou_a, point.senkou_b)
    bullish_cloud = point.senkou_a > point.senkou_b
    return above_cloud and bullish_cloud


def as_of(points_4h: list[IchimokuPoint], timestamp: datetime) -> IchimokuPoint | None:
    """BR6: most recently closed 4h point at or before `timestamp`. Assumes points_4h sorted ascending."""
    candidate = None
    for point in points_4h:
        if point.candle_time > timestamp:
            break
        candidate = point
    return candidate
