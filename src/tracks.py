"""BR25: 보유 기간이 다른 4개 추천 트랙 — 초단기 / 단기 / 중기 / 장기.

BR24(반감기 사이클 90일 트랙)를 대체한다. 반감기 여부와 무관하게 동작하며, 게이트는 시장 국면
(BR23을 확장한 3단계: 약상승장 / 상승장 / 강세장)이 담당한다.

**진입은 구름대 돌파다** -- "직전 봉은 구름 위가 아니었고 이번 봉 종가가 구름 위". 어느 타임프레임의
돌파가 가장 좋은지는 실측으로 정했다 (5종목 × 365일):

| 타임프레임 | 돌파수 | 초단기 +2%/8h | 단기 +3.5%/12h | 중기 +5%/24h |
|---|---|---|---|---|
| 5m | 15,653 | 20.6% | 11.3% | 11.4% |
| 15m | 5,043 | 20.8% | 11.1% | 10.9% |
| 30m | 2,343 | 22.0% | 11.4% | 11.5% |
| 1h | 1,186 | 21.0% | 10.0% | **14.1%** |
| **4h** | 277 | **25.1%** | **14.6%** | 13.7% |
| 1d | 22 | 22.7% | 9.1% | 4.5% |

4시간봉이 초단기·단기에서 1위, 중기는 1시간봉이 근소 우위다. 1분/3분/5분봉은 돌파 건수만 많고
확률은 낮아 수집 대상에서 뺐다(23GB를 쓰고 이득이 창마다 부호가 갈렸다).
"""

from dataclasses import dataclass

from src.data_store import Candle, close_time
from src.features import IchimokuPoint

ULTRA = "ultra"
SHORT = "short"
MID = "mid"
LONG = "long"


@dataclass(frozen=True)
class TrackSpec:
    key: str
    label: str
    target: float
    stop: float
    hold_hours: int
    timeframe: str  # 진입 판정에 쓰는 봉
    min_samples: int = 10


# 목표·보유는 사용자 지정. 진입 타임프레임과 손절은 실측으로 정했다.
# 장기는 최초 요청(48시간 +15%)이 실측 9%로 성립하지 않아 "목표 하향 + 보유 연장" 지시에 따라
# +10%/-7%/7일로 재설정했다(실측 도달률 32%, 기대수익 +0.2%).
TRACKS = (
    TrackSpec(ULTRA, "초단기", 0.02, 0.02, 8, "4h"),
    TrackSpec(SHORT, "단기", 0.03, 0.02, 12, "4h"),
    TrackSpec(MID, "중기", 0.05, 0.03, 24, "1h"),
    TrackSpec(LONG, "장기", 0.10, 0.07, 168, "4h"),
)
TRACK_BY_KEY = {t.key: t for t in TRACKS}

# 수집 대상 타임프레임. 1m/3m/5m은 제외한다 -- 20종 9년 기준 23GB를 쓰는데 초단기 기여가
# 창마다 부호가 갈렸다(90일 창 +2.5%p, 365일 창 -4.5%p). 1m은 BR22 가격 감시가 저장 없이
# 실시간 조회하므로 여기 없어도 알림 정밀도는 그대로다.
COLLECTED_TIMEFRAMES = ("15m", "30m", "1h", "4h", "1d", "1w", "1M")

# 타임프레임별 수집 깊이(일). 짧은 봉에 긴 이력을 요구하면 페이지 수가 폭증한다 --
# 15분봉 9년은 315,360봉 = 316페이지로 _MAX_PAGES(150)를 넘어 **조용히 절단**된다.
# 트랙에 필요한 것은 최대 이력이 아니라 충분한 표본이므로 짧은 봉일수록 얕게 받는다.
#   15m 2년 = 70,080봉(71페이지) / 30m 3년 = 52,560봉(53페이지) / 1h·4h는 가용 최대
LOOKBACK_DAYS_BY_TIMEFRAME = {
    "15m": 730,
    "30m": 1095,
}

# 각 타임프레임의 시간 길이. 1M(월봉)은 길이가 고르지 않으므로 근사값이며, 보유 기간 환산에는
# 쓰지 않는다(트랙의 진입 타임프레임은 4h/1h뿐이다).
TIMEFRAME_HOURS = {
    "15m": 0.25,
    "30m": 0.5,
    "1h": 1.0,
    "4h": 4.0,
    "1d": 24.0,
    "1w": 168.0,
    "1M": 730.0,
}


def bars_for(spec: TrackSpec) -> int:
    """보유 기간을 해당 타임프레임의 봉 수로 환산."""
    return max(1, round(spec.hold_hours / TIMEFRAME_HOURS[spec.timeframe]))


def cloud_breakout(points: list[IchimokuPoint], i: int) -> bool:
    """BR25: 직전 봉은 구름 위가 아니었고 이번 봉 종가가 구름 위 -- '뚫는 순간'.

    BR24에서는 '구름 위 상태'를 썼지만 그건 90일 보유가 전제였다. 8~168시간 보유에서는
    돌파 시점이 기준이 되어야 진입가가 움직임의 시작에 붙는다."""
    if i <= 0 or i >= len(points):
        return False
    point, previous = points[i], points[i - 1]
    if None in (point.senkou_a, point.senkou_b, previous.senkou_a, previous.senkou_b):
        return False
    return point.close > max(point.senkou_a, point.senkou_b) and previous.close <= max(
        previous.senkou_a, previous.senkou_b
    )


def simulate(candles: list[Candle], i: int, spec: TrackSpec) -> tuple[str, float, int] | None:
    """목표/손절 중 먼저 닿는 쪽으로 판정. 보유 창이 안 차면 판정 불가(None).

    단기 트랙 `simulate_trade`와 같은 규칙이다 -- 데이터 끝에서 잘라 타임아웃으로 세면 진행 중인
    매매가 표본에 섞인다(BR24 구현에서 실제로 겪은 결함)."""
    bars = bars_for(spec)
    if i + bars >= len(candles):
        return None
    entry = candles[i].close
    if entry <= 0:
        return None
    target, stop = entry * (1 + spec.target), entry * (1 - spec.stop)
    for j in range(i + 1, i + 1 + bars):
        if candles[j].low <= stop:
            return "loss", -spec.stop, j
        if candles[j].high >= target:
            return "win", spec.target, j
    last = i + bars
    return "timeout", candles[last].close / entry - 1, last


def compute_track_stats(candles: list[Candle], points: list[IchimokuPoint], spec: TrackSpec):
    """해당 코인 이력에서 같은 조건으로 진입했던 과거 시점의 성적.

    보유 중에는 새 진입을 잡지 않는다(겹침 제거) -- 겹치는 진입을 각각 세면 같은 구간이 여러 번
    반영되어 표본이 부풀고 확률이 왜곡된다."""
    wins = losses = timeouts = 0
    returns: list[float] = []
    drawdowns: list[float] = []
    last_exit = -1
    for i in range(len(points)):
        if i <= last_exit or not cloud_breakout(points, i):
            continue
        simulated = simulate(candles, i, spec)
        if simulated is None:
            continue
        result, ret, exit_index = simulated
        entry = candles[i].close
        drawdowns.append(min((candles[j].low / entry - 1) for j in range(i + 1, exit_index + 1)))
        last_exit = exit_index
        returns.append(ret)
        wins += result == "win"
        losses += result == "loss"
        timeouts += result == "timeout"
    n = len(returns)
    return {
        "n": n,
        "hit_count": wins,
        "loss_count": losses,
        "timeout_count": timeouts,
        "hit_rate": (wins / n) if n else None,
        "expected_return": (sum(returns) / n) if n else None,
        "max_drawdown": min(drawdowns) if drawdowns else None,
    }


def latest_entry(candles: list[Candle], points: list[IchimokuPoint]) -> int | None:
    """가장 최근 마감봉이 돌파 봉이면 그 인덱스."""
    if not points:
        return None
    i = len(points) - 1
    return i if cloud_breakout(points, i) else None


def entry_time_of(candles: list[Candle], i: int):
    return close_time(candles[i])
