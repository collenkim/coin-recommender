"""BR24: 장기 트랙 — 반감기 사이클 기반 추천.

단기 트랙(BR18~BR21, 24시간 +3%)과 **완전히 분리된** 규칙이다. 게이트·진입조건·매매규칙·표본이
전부 다르고, 서로의 수치를 공유하지 않는다. 같은 모듈에 두면 상수 이름이 겹치고(TARGET_RETURN 등)
한쪽 조정이 다른 쪽으로 새어 들어가므로 파일을 나눈다.

왜 나누는가(실측): BTC 가격은 반감기 직후 1년에 뚜렷이 강하지만(이후 30일 +5.61%/상승 63%,
기저 +1.01%/54%), **같은 구간의 24시간 매매 적중률은 33.6%로 오히려 최저**다. "가격이 오른다"와
"24시간 안에 +3%를 먼저 찍는다"는 다른 사건이라 하나의 규칙으로 처리할 수 없다.
"""

from dataclasses import dataclass
from datetime import datetime, timedelta, timezone

from src.backtest import TradeOutcome, aggregate_stats
from src.data_store import Candle, close_time
from src.features import IchimokuPoint

# --- 반감기 사이클 (BR24) ---
# 2028년분은 추정치다. 실제 반감기는 블록 높이로 결정되므로 근접하면 실제 일자로 교체해야 한다.
HALVINGS = (
    datetime(2012, 11, 28, tzinfo=timezone.utc),
    datetime(2016, 7, 9, tzinfo=timezone.utc),
    datetime(2020, 5, 11, tzinfo=timezone.utc),
    datetime(2024, 4, 20, tzinfo=timezone.utc),
    datetime(2028, 4, 20, tzinfo=timezone.utc),
)
_DAYS_PER_YEAR = 365.25

# 열어 둘 사이클 연차. 실측 기대수익: 0~1년차 +2.66% / 1~2년차 -0.13% / 2~3년차 +0.80% /
# 3~4년차 +1.43%. 1~2년차만 음수여서 닫는다. 2~3년차는 사용자 결정으로 연다(0.7년 뒤 열리는
# 3~4년차가 더 나은 구간이지만 이번 범위가 아니다).
OPEN_CYCLE_YEARS = (0, 2)

# --- 매매 규칙 (BR24) ---
# 4시간봉 540개 = 90일. 손절 -10%는 **측정과 반대되는 사용자 결정**이다: 실측상 -20%가
# 기대수익 5.24% vs -10% 3.79%로 우월하고, -10%는 최종 승자의 43.3%를 먼저 잘라낸다
# (승자의 도달 전 최대 눌림 중앙값 8.4%, p75 18.7%). 재검토 시 business-rules.md BR24 표 참조.
LONG_TARGET_RETURN = 0.20
LONG_STOP_LOSS = 0.10
LONG_HOLD_BARS_4H = 540

# --- 진입 조건 (BR24) ---
# 최근 7일 평균 거래량 / 그 이전 23일 평균. 4시간봉 기준 42봉 / (180-42)봉.
LONG_VOLUME_RECENT_BARS = 42
LONG_VOLUME_WINDOW_BARS = 180
LONG_VOLUME_MULTIPLE = 1.3

# 단기 트랙과 같은 사유의 표본 하한. 2~3년차에서는 이 하한이 "안전하게"의 실질적 장치로 작동한다 --
# 신규 상장 종목은 해당 연차 표본이 1~3건이라 자동 탈락하고, 이력이 긴 8종만 남는다.
LONG_MIN_SAMPLES = 10


@dataclass(frozen=True)
class CyclePosition:
    halving: datetime
    year: int  # 반감기 후 경과 연차 (0=0~1년차)
    elapsed_years: float
    is_open: bool


def cycle_position(moment: datetime) -> CyclePosition | None:
    """`moment`가 속한 반감기 사이클 위치. 첫 반감기 이전이면 None."""
    past = [h for h in HALVINGS if h <= moment]
    if not past:
        return None
    halving = max(past)
    elapsed = (moment - halving).days / _DAYS_PER_YEAR
    year = int(elapsed)
    return CyclePosition(halving=halving, year=year, elapsed_years=elapsed, is_open=year in OPEN_CYCLE_YEARS)


def next_open_at(moment: datetime) -> datetime | None:
    """게이트가 다음에 열리는 시각. 이미 열려 있으면 None -- 알림에 "언제 열리는지"를 적기 위함."""
    position = cycle_position(moment)
    if position is None or position.is_open:
        return None
    for year in sorted(OPEN_CYCLE_YEARS):
        opens = position.halving + timedelta(days=year * _DAYS_PER_YEAR)
        if opens > moment:
            return opens
    later = [h for h in HALVINGS if h > moment]
    return min(later) if later else None


def volume_ratio(candles_4h: list[Candle], i: int) -> float | None:
    """최근 7일 평균 / 그 이전 23일 평균. 기준선 구간이 없으면 None."""
    if i + 1 < LONG_VOLUME_WINDOW_BARS:
        return None
    recent = candles_4h[i + 1 - LONG_VOLUME_RECENT_BARS : i + 1]
    baseline = candles_4h[i + 1 - LONG_VOLUME_WINDOW_BARS : i + 1 - LONG_VOLUME_RECENT_BARS]
    if not baseline:
        return None
    baseline_mean = sum(c.volume for c in baseline) / len(baseline)
    if baseline_mean <= 0:
        return None
    return (sum(c.volume for c in recent) / len(recent)) / baseline_mean


def long_entry_signal(candles_4h: list[Candle], points_4h: list[IchimokuPoint], i: int) -> bool:
    """BR24: 4시간봉 종가가 구름 위이고 거래량이 기준선의 1.3배를 넘는 봉.

    **구름을 뚫는 순간이 아니라 구름 위에 있는 상태다.** 돌파 순간은 실측상 2024 사이클에서 우위가
    사라졌고(+2.8%p/+0.8%p/-0.9%p) 표본도 198건으로 얇았다.

    모멘텀 조건(직전 30일 수익률)은 의도적으로 넣지 않는다 -- 필터로 쓰면 두 사이클 모두 기저
    미만이고(-2.5%p/-1.5%p), 사이클 조건과 결합하면 2020 우위가 +12.6%p에서 +0.9%p로 붕괴한다.
    """
    if i >= len(points_4h) or i >= len(candles_4h):
        return False
    point = points_4h[i]
    if point.senkou_a is None or point.senkou_b is None:
        return False
    if point.close <= max(point.senkou_a, point.senkou_b):
        return False
    ratio = volume_ratio(candles_4h, i)
    return ratio is not None and ratio > LONG_VOLUME_MULTIPLE


def simulate_long_trade(candles_4h: list[Candle], i: int) -> tuple[TradeOutcome, int] | None:
    """진입 후 목표/손절 중 먼저 닿는 쪽으로 판정하고, 90일 안에 둘 다 없으면 종가 청산.

    반환값의 두 번째는 **실제 청산 봉 인덱스**다. 겹침 제거가 고정 보유기간이 아니라 실제 청산
    시점을 기준으로 해야 측정치와 일치한다(단기 트랙은 24봉 고정이라 이 구분이 필요 없었다).

    아직 540봉(90일)이 지나지 않은 진입은 **판정 불가이므로 None**이다 -- 단기 트랙
    `simulate_trade`와 같은 규칙이다. 데이터 끝에서 잘라 타임아웃으로 세면 진행 중인 매매가
    표본에 섞인다. 개방 직후 구간(예: 2~3년차 시작 4개월 시점)은 거의 전부가 미완료라
    이 처리가 없으면 표본 수와 확률이 통째로 왜곡된다."""
    window_end = i + LONG_HOLD_BARS_4H
    if window_end >= len(candles_4h):
        return None
    entry = candles_4h[i].close
    if entry <= 0:
        return None
    target = entry * (1 + LONG_TARGET_RETURN)
    stop = entry * (1 - LONG_STOP_LOSS)
    last = window_end
    drawdown = 0.0
    for j in range(i + 1, last + 1):
        drawdown = min(drawdown, candles_4h[j].low / entry - 1)
        if candles_4h[j].low <= stop:
            return TradeOutcome(result="loss", ret=-LONG_STOP_LOSS, drawdown=drawdown), j
        if candles_4h[j].high >= target:
            return TradeOutcome(result="win", ret=LONG_TARGET_RETURN, drawdown=drawdown), j
    return TradeOutcome(result="timeout", ret=candles_4h[last].close / entry - 1, drawdown=drawdown), last


def compute_long_stats(market: str, candles_4h: list[Candle], points_4h: list[IchimokuPoint], cycle_year: int):
    """BR24: **현재와 같은 사이클 연차**의 과거 진입만 표본으로 쓴다.

    단기 트랙이 레짐 게이트가 켜진 구간의 표본만 쓰는 것과 같은 방식이다. 2~3년차에 0~1년차의
    42.1%를 표시하면 과대 표시가 된다(실측 2~3년차는 35.8%).

    보유 중에는 새 진입을 잡지 않는다 -- 겹치는 진입을 각각 세면 같은 구간이 여러 번 반영된다.
    실제로 4시간봉마다 세면 6,077건이지만 겹침을 제거하면 448건이다."""
    results: list[TradeOutcome] = []
    last_exit = -1
    for i in range(len(points_4h)):
        if i <= last_exit:
            continue
        if not long_entry_signal(candles_4h, points_4h, i):
            continue
        position = cycle_position(close_time(candles_4h[i]))
        if position is None or position.year != cycle_year:
            continue
        simulated = simulate_long_trade(candles_4h, i)
        if simulated is None:
            continue
        outcome, exit_index = simulated
        last_exit = exit_index
        results.append(outcome)
    return aggregate_stats(market, results)
