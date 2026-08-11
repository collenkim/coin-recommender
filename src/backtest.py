import math
from dataclasses import dataclass
from datetime import datetime, timedelta

from src.data_store import Candle
from src.features import IchimokuPoint

# --- 매매 규칙 (BR18) ---
# 5년/바이낸스 27마켓/579,755봉 실측으로 정한 값. 목표 +3%는 사용자 결정(+4%는 어떤 코인도
# 도달한 적이 없어 구조적으로 통과 불가였음 -- 5년 표본 기준 코인별 기대수익률 최댓값이 +2.68%).
TARGET_RETURN = 0.03
STOP_LOSS = 0.02
FORWARD_BARS_1H = 24  # 24h forward window on 1h candles

# --- 진입 조건 (BR19): 거래량 확인 돌파 ∩ 추세 지속 ---
BREAKOUT_BARS = 24
VOLUME_MULTIPLE = 2.0
KIJUN_RISE_BARS = 6

# --- 레짐 게이트 (BR20) ---
# 180봉 x 4h = 30일. 강한 상승장과 반등 상승장에서만 진입한다 -- 그 외 구간은 실측 목표달성률이
# 기저와 구분되지 않는다 (강한상승 59.7% / 반등 55.5% vs 일반상승 48.3% / 하락 48.2%, 손절 없음 기준).
REGIME_BARS_30D = 180
STRONG_BULL_30D = 0.20
REBOUND_OFF_LOW = 0.10
STRONG_BULL = "strong_bull"
REBOUND = "rebound"

# --- 추천 하한 (BR21) ---
MIN_SIGNAL_SAMPLES = 3
# 손절 -2%를 적용했을 때 강한상승 레짐의 실측 목표달성률이 40.7%. 자기 이력에서 이보다 못한
# 코인은 레짐 평균만도 못하다는 뜻이므로 제외한다.
MIN_HIT_RATE = 0.40


@dataclass(frozen=True)
class SignalStats:
    market: str
    n: int
    hit_count: int
    hit_rate: float | None  # 손절 -2%를 치기 전에 목표 +3%에 도달한 비율
    hit_rate_lower: float | None  # 위 비율의 95% 신뢰 하한 (표본 3건짜리 100%를 걸러내기 위함)
    expected_return: float | None  # 목표/손절 규칙을 적용했을 때의 평균 수익
    max_drawdown: float | None


@dataclass(frozen=True)
class TradeOutcome:
    result: str  # "win" | "loss" | "timeout"
    ret: float
    drawdown: float


@dataclass(frozen=True)
class RecommendationOutcome:
    market: str
    run_time: datetime
    target_reached: bool
    realized_return: float
    evaluated_at: datetime


def wilson_lower(hits: int, n: int, z: float = 1.96) -> float:
    """비율의 95% 신뢰 하한. 3/3을 1.00이 아니라 0.44로 돌려주므로, 표본이 얇은 코인이 적중률
    100%로 목록 상단을 차지하는 일을 막는다."""
    if n <= 0:
        return 0.0
    p = hits / n
    denom = 1 + z * z / n
    centre = p + z * z / (2 * n)
    margin = z * math.sqrt((p * (1 - p) + z * z / (4 * n)) / n)
    return max(0.0, (centre - margin) / denom)


def build_regime_series(btc_candles_4h: list[Candle]) -> list[tuple[datetime, str | None]]:
    """BR20: 각 4시간봉 시점의 레짐. 30일 이력이 쌓이기 전 구간은 None(진입 금지)이다.

    라이브와 백테스트가 같은 함수를 쓰므로 두 경로가 어긋날 수 없다 -- 이 코드베이스에서
    반복적으로 문제가 됐던 지점이라 의도적으로 하나로 둔다."""
    series: list[tuple[datetime, str | None]] = []
    for i, candle in enumerate(btc_candles_4h):
        if i < REGIME_BARS_30D:
            series.append((candle.candle_time, None))
            continue
        close = candle.close
        ret_30d = close / btc_candles_4h[i - REGIME_BARS_30D].close - 1
        low_30d = min(c.close for c in btc_candles_4h[i - REGIME_BARS_30D + 1 : i + 1])
        off_low = close / low_30d - 1
        if ret_30d > STRONG_BULL_30D:
            series.append((candle.candle_time, STRONG_BULL))
        elif ret_30d <= 0 and off_low > REBOUND_OFF_LOW:
            series.append((candle.candle_time, REBOUND))
        else:
            series.append((candle.candle_time, None))
    return series


def regime_as_of(series: list[tuple[datetime, str | None]], timestamp: datetime) -> str | None:
    """`timestamp` 이전에 마감된 가장 최근 4시간봉의 레짐. 이력보다 이른 시점이면 None."""
    current = None
    for candle_time, regime in series:
        if candle_time > timestamp:
            break
        current = regime
    return current


def entry_signal(candles_1h: list[Candle], points_1h: list[IchimokuPoint], i: int) -> bool:
    """BR19: 종가가 직전 24시간 고가를 돌파하고 거래량이 24시간 평균의 2배를 넘으면서,
    구름 위 + 전환선 > 기준선 + 기준선 상승(6봉 전 대비)인 봉.

    5년 21분기 중 16분기에서 무조건부 기저 대비 우위였고, 강한 상승장 목표달성률 59.7%로
    시험한 조건 중 가장 높았다."""
    if i < BREAKOUT_BARS or i >= len(points_1h) or i >= len(candles_1h):
        return False
    point = points_1h[i]
    if None in (point.tenkan, point.kijun, point.senkou_a, point.senkou_b):
        return False
    if point.close <= max(point.senkou_a, point.senkou_b):
        return False
    if point.tenkan <= point.kijun:
        return False
    prev_kijun = points_1h[i - KIJUN_RISE_BARS].kijun if i >= KIJUN_RISE_BARS else None
    if prev_kijun is None or point.kijun <= prev_kijun:
        return False

    breakout_window = candles_1h[i - BREAKOUT_BARS : i]
    if candles_1h[i].close <= max(c.high for c in breakout_window):
        return False
    volume_window = candles_1h[i - BREAKOUT_BARS + 1 : i + 1]
    average_volume = sum(c.volume for c in volume_window) / len(volume_window)
    return average_volume > 0 and candles_1h[i].volume > VOLUME_MULTIPLE * average_volume


def simulate_trade(candles_1h: list[Candle], i: int) -> TradeOutcome | None:
    """BR18: 목표가와 손절가 중 무엇을 먼저 치는지를 봉 단위로 겨룬다.

    한 봉 안에서 고가가 목표를, 저가가 손절을 동시에 만족하면 OHLC만으로는 선후를 알 수 없다.
    손절이 먼저 체결됐다고 보수적으로 판정한다 -- 결과를 좋게 보이게 만드는 쪽이 아니다.

    아직 24봉이 지나지 않은 진입은 판정 불가이므로 None을 돌려준다."""
    window = candles_1h[i + 1 : i + 1 + FORWARD_BARS_1H]
    if len(window) < FORWARD_BARS_1H:
        return None

    entry = candles_1h[i].close
    target_price = entry * (1 + TARGET_RETURN)
    stop_price = entry * (1 - STOP_LOSS)
    worst = 0.0
    for candle in window:
        worst = min(worst, (candle.low - entry) / entry)
        if candle.low <= stop_price:
            return TradeOutcome(result="loss", ret=-STOP_LOSS, drawdown=worst)
        if candle.high >= target_price:
            return TradeOutcome(result="win", ret=TARGET_RETURN, drawdown=worst)
    return TradeOutcome(result="timeout", ret=(window[-1].close - entry) / entry, drawdown=worst)


def compute_signal_stats(
    market: str,
    candles_1h: list[Candle],
    points_1h: list[IchimokuPoint],
    regime_series: list[tuple[datetime, str | None]],
) -> SignalStats:
    """BR21: 해당 코인의 전체 이력에서 진입 조건 + 레짐을 모두 만족한 과거 시점을 찾아
    목표/손절 규칙으로 판정한 성적.

    보유 중에는 새 진입을 잡지 않는다(24봉 겹침 제거). 겹치는 진입을 각각 세면 같은 구간의
    결과가 여러 번 반영되어 표본 수가 부풀고 확률이 왜곡된다."""
    results: list[TradeOutcome] = []
    last_exit = -1
    for i in range(len(points_1h)):
        if i <= last_exit:
            continue
        if not entry_signal(candles_1h, points_1h, i):
            continue
        if regime_as_of(regime_series, points_1h[i].candle_time) is None:
            continue
        outcome = simulate_trade(candles_1h, i)
        if outcome is None:
            continue
        last_exit = i + FORWARD_BARS_1H
        results.append(outcome)

    return aggregate_stats(market, results)


def aggregate_stats(market: str, results: list[TradeOutcome]) -> SignalStats:
    """n=0이면 확률은 계산 불가(0이 아니라 None)."""
    n = len(results)
    if n == 0:
        return SignalStats(market=market, n=0, hit_count=0, hit_rate=None, hit_rate_lower=None, expected_return=None, max_drawdown=None)
    hit_count = sum(1 for r in results if r.result == "win")
    return SignalStats(
        market=market,
        n=n,
        hit_count=hit_count,
        hit_rate=hit_count / n,
        hit_rate_lower=wilson_lower(hit_count, n),
        expected_return=sum(r.ret for r in results) / n,
        max_drawdown=min(r.drawdown for r in results),
    )


def evaluate_outcome(market: str, run_time: datetime, candles_1h: list[Candle], now: datetime) -> RecommendationOutcome | None:
    """BR11: 과거 추천 1건을 사후 판정한다. 판정 규칙은 `simulate_trade`와 동일해야 한다 --
    추천할 때 쓴 확률과 사후에 매기는 성패가 다른 기준이면 적중률 기록이 의미를 잃는다.

    아직 판정할 데이터가 모이지 않았으면 None (호출자가 다음 회차에 재시도)."""
    entry_index = None
    for index, candle in enumerate(candles_1h):
        if candle.candle_time > run_time:
            break
        entry_index = index

    if entry_index is None:
        return None

    outcome = simulate_trade(candles_1h, entry_index)
    if outcome is None:
        return None

    return RecommendationOutcome(
        market=market,
        run_time=run_time,
        target_reached=outcome.result == "win",
        realized_return=outcome.ret,
        evaluated_at=now,
    )
