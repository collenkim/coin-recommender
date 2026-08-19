import math
from dataclasses import dataclass
from datetime import datetime, timedelta

from src.data_store import Candle, close_time
from src.features import IchimokuPoint

# --- 매매 규칙 (BR18) ---
# 5년/바이낸스 27마켓/579,755봉 실측으로 정한 값. 목표 +3%는 사용자 결정(+4%는 어떤 코인도
# 도달한 적이 없어 구조적으로 통과 불가였음 -- 5년 표본 기준 코인별 기대수익률 최댓값이 +2.68%).
TARGET_RETURN = 0.03
STOP_LOSS = 0.02
FORWARD_BARS_1H = 24  # 24h forward window on 1h candles

# --- 진입 조건 (BR19): 거래량 확인 돌파 ∩ 추세 지속 ---
# 돌파 구간과 거래량 기준선은 반드시 분리한다. 하나로 묶으면 돌파를 4시간으로 줄일 때
# 거래량 조건이 "직전 4시간 평균의 2배"로 함께 약해져, 무엇 때문에 결과가 변했는지 알 수 없다.
BREAKOUT_BARS = 4
VOLUME_BASELINE_BARS = 24
VOLUME_MULTIPLE = 2.0
KIJUN_RISE_BARS = 6

# --- 레짐 게이트 (BR20) ---
# 180봉 x 4h = 30일. 강한 상승장과 반등 상승장에서만 진입한다 -- 그 외 구간은 실측 목표달성률이
# 기저와 구분되지 않는다 (강한상승 59.7% / 반등 55.5% vs 일반상승 48.3% / 하락 48.2%, 손절 없음 기준).
REGIME_BARS_30D = 180
STRONG_BULL_30D = 0.20
REBOUND_OFF_LOW = 0.10
# 1200봉 x 4h = 200일. 반등은 **장기 상승 추세 안의 조정 후 반등**일 때만 인정한다.
# 장기 하락 추세의 반등은 거짓 반등이라는 판단이며, 알트는 BTC/ETH에 끌려다니므로
# BTC가 구조적 하락 국면이면 알트가 독립적으로 오를 수 없다는 구조적 근거를 따른다.
REGIME_MA_BARS = 1200
# 200일 이동평균 워밍업분. BTC 4시간봉은 이만큼 더 깊게 수집해야 백테스트 구간 전체에서
# 반등 판정이 가능하다.
REGIME_WARMUP_DAYS = 210
STRONG_BULL = "strong_bull"
REBOUND = "rebound"

# --- 추천 하한 (BR21) ---
# 적중률 필터가 원시 비율을 쓰므로(하한이 아니라), 표본이 얇으면 "n=4에 2승 = 50%"가 그대로
# 45% 문턱을 넘는다. 표본 하한이 그걸 막는 안전장치다. 10으로 잡은 근거: 12년 lookback에서
# 코인당 실측 n이 활발한 종목 110~183, 나머지도 29~43이라 정상 종목은 여유 있게 넘는다.
# (5년 lookback 시절 근거는 52~79였다 -- 2026-08-18 lookback 확대로 값만 갱신, 하한 10은 유지.)
MIN_SIGNAL_SAMPLES = 10
# BR26(2026-08-19): 45% -> 30%. 45%는 **실측 능력보다 높은 문턱**이었다 -- 9년 5,145 독립매매
# 기준 전체 적중률이 36.3%이고, 국면을 나눠도 강세장 35.8% / 상승장 37.3% / 약상승장 34.1%로
# 어디서도 45%에 닿지 않는다. 그래서 통과하는 코인은 실력이 아니라 표본에서 우연히 높게 나온
# 쪽이었고, 워크포워드 실측이 그것을 보여준다: 선택군의 이후 실제 성적 38.9% vs 표시 45%(-6.1%p).
# 30%는 실측 평균(36.3%) 아래이므로 같은 선택 편향을 만들지 않는다.
MIN_HIT_RATE = 0.30


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
    """BR20: 각 4시간봉의 레짐을, 그 봉이 **마감된 시각**에 붙여 돌려준다.

    `candle_time`은 시가 시각이므로 그대로 쓰면 08:00봉의 레짐이 09:00 시점에도 조회된다 --
    그 봉은 12:00에야 마감되므로 아직 모르는 종가를 쓰는 룩어헤드가 된다. 라이브는 마감된 봉만
    저장해 영향이 없지만 백테스트만 낙관적으로 나오는 train/serve 불일치가 생긴다.

    라이브와 백테스트가 같은 함수를 쓰므로 두 경로가 어긋날 수 없다 -- 이 코드베이스에서
    반복적으로 문제가 됐던 지점이라 의도적으로 하나로 둔다."""
    closes = [c.close for c in btc_candles_4h]
    # 200일 이동평균을 매 봉마다 1,200개씩 더하면 O(n x 1200)이 된다. 누적합으로 O(n).
    prefix = [0.0]
    for close in closes:
        prefix.append(prefix[-1] + close)

    series: list[tuple[datetime, str | None]] = []
    for i, candle in enumerate(btc_candles_4h):
        if i < REGIME_BARS_30D:
            series.append((close_time(candle), None))
            continue
        close = closes[i]
        ret_30d = close / closes[i - REGIME_BARS_30D] - 1
        off_low = close / min(closes[i - REGIME_BARS_30D + 1 : i + 1]) - 1
        if ret_30d > STRONG_BULL_30D:
            series.append((close_time(candle), STRONG_BULL))
        elif ret_30d <= 0 and off_low > REBOUND_OFF_LOW and _above_long_term_trend(closes, prefix, i):
            series.append((close_time(candle), REBOUND))
        else:
            series.append((close_time(candle), None))
    return series


def _above_long_term_trend(closes: list[float], prefix: list[float], i: int) -> bool:
    """BTC가 200일 이동평균 위인가. 확인할 이력이 없으면 False -- 장기 추세를 모르는 채로
    반등에 진입하지 않는다.

    반등 조건에만 적용한다. 강한 상승장(30일 +20% 초과)은 그 자체로 추세가 확인되므로
    이 조건을 요구하지 않으며, 짧게 열렸다 닫히는 개방 구간도 그대로 통과한다."""
    if i < REGIME_MA_BARS:
        return False
    moving_average = (prefix[i + 1] - prefix[i + 1 - REGIME_MA_BARS]) / REGIME_MA_BARS
    return closes[i] > moving_average


def regime_as_of(series: list[tuple[datetime, str | None]], timestamp: datetime) -> str | None:
    """`timestamp` 이전에 마감된 가장 최근 4시간봉의 레짐. 이력보다 이른 시점이면 None."""
    current = None
    for candle_time, regime in series:
        if candle_time > timestamp:
            break
        current = regime
    return current


def entry_signal(candles_1h: list[Candle], points_1h: list[IchimokuPoint], i: int) -> bool:
    """BR19: 종가가 직전 4시간 고가를 돌파하고 거래량이 24시간 평균의 2배를 넘으면서,
    구름 위 + 전환선 > 기준선 + 기준선 상승(6봉 전 대비)인 봉.

    5년 21분기 중 16분기에서 무조건부 기저 대비 우위였고, 강한 상승장 목표달성률 59.7%로
    시험한 조건 중 가장 높았다.

    돌파 구간은 실측상 거의 영향이 없다 -- 4/6/8/12/24시간 모두 목표달성률 38.7~39.2%로
    같고 매매 수만 935/919/911/898/874로 달라진다. 거래량이 24시간 평균의 2배로 터지는
    순간이면 어차피 어느 구간 기준으로도 신고가이기 때문에, 실질 병목은 거래량 조건이다.
    4시간을 쓰는 것은 품질 손실 없이 매매 기회가 7% 많기 때문이다."""
    if i < max(BREAKOUT_BARS, VOLUME_BASELINE_BARS) or i >= len(points_1h) or i >= len(candles_1h):
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
    volume_window = candles_1h[i - VOLUME_BASELINE_BARS + 1 : i + 1]
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


