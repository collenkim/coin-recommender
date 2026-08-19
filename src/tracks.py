"""BR25: 보유 기간이 다른 4개 추천 트랙 — 초단기 / 단기 / 중기 / 장기.

BR24(반감기 사이클 90일 트랙)를 대체한다. 반감기 여부와 무관하게 동작하며, 게이트는 시장 국면
(BR23을 확장한 3단계: 약상승장 / 상승장 / 강세장)이 담당한다.

**진입은 전환선/기준선 골든크로스다** (BR27로 구름대 돌파에서 교체). 구름 돌파는 어느 타임프레임의
돌파가 가장 좋은지 실측으로 4시간봉을 골랐었다 (5종목 × 365일):

| 타임프레임 | 돌파수 | 초단기 +2%/8h | 단기 +3.5%/12h | 중기 +5%/24h |
|---|---|---|---|---|
| 5m | 15,653 | 20.6% | 11.3% | 11.4% |
| 15m | 5,043 | 20.8% | 11.1% | 10.9% |
| 30m | 2,343 | 22.0% | 11.4% | 11.5% |
| 1h | 1,186 | 21.0% | 10.0% | **14.1%** |
| **4h** | 277 | **25.1%** | **14.6%** | 13.7% |
| 1d | 22 | 22.7% | 9.1% | 4.5% |

1분/3분/5분봉은 돌파 건수만 많고 확률은 낮아 수집 대상에서 뺐다(23GB를 쓰고 이득이 창마다
부호가 갈렸다).

**BR27(2026-08-19)에서 두 가지를 바꿨다** -- 전 트랙 실측 결과 신호와 판정 해상도 모두에서
일관된 개선이 나왔다:

| 트랙 | 이전(구름돌파·진입판정 동일봉) | 이후(골든크로스·진입 4h·판정 30m) |
|---|---|---|
| 초단기 | -0.03% | **+0.15%** |
| 단기 | +0.03% | **+0.22%** |
| 중기 | +0.09% | **+0.26%** |
| 장기 | +0.37% | **+0.56%** |

**판정 해상도를 진입봉과 분리한 이유**: 8시간 보유를 4시간봉으로 판정하면 봉이 2개뿐이라, 한 봉에서
목표·손절이 겹칠 때 손절로 간주하는 보수적 규칙이 과하게 작동한다. 거친 해상도는 **손실 쪽으로
편향**되므로 세분할수록 참값에 가깝다.
"""

from bisect import bisect_right
from dataclasses import dataclass
from datetime import datetime

from src.data_store import Candle, close_time
from src.features import IchimokuPoint, above_cloud

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
    timeframe: str  # 진입 신호를 찾는 봉
    # BR27: 목표/손절 도달을 판정하는 봉. 진입봉과 분리한다 -- 같은 봉으로 판정하면 보유 기간이
    # 짧은 트랙일수록 판정 봉수가 적어 손실 쪽으로 편향된다.
    sim_timeframe: str = "30m"
    # BR27: 진입 봉이 구름 위일 것을 추가로 요구할지. 장기에서만 유효했다
    # (장기 +0.56% -> +1.06%). 초단기는 오히려 손해(+0.15% -> +0.12%)라 켜지 않는다.
    require_above_cloud: bool = False
    min_samples: int = 10


# 목표·보유는 사용자 지정. 진입 타임프레임과 손절은 실측으로 정했다.
# 장기는 최초 요청(48시간 +15%)이 실측 9%로 성립하지 않아 "목표 하향 + 보유 연장" 지시에 따라
# +10%/-7%/7일로 재설정했다(실측 도달률 32%, 기대수익 +0.2%).
# 트랙은 **목표와 보유 기간의 정의일 뿐**이며 트랙별 전용 국면은 두지 않는다. 게이트(BR25)가
# 연 국면에서는 네 트랙이 모두 동작한다.
# BR27 실측으로 네 트랙 모두 진입 4시간봉 / 판정 30분봉이 최적이었다(중기는 진입봉이 1h -> 4h로
# 바뀌었다: 1h 진입 +0.01% vs 4h 진입 +0.26%).
TRACKS = (
    TrackSpec(ULTRA, "초단기", 0.02, 0.02, 8, "4h"),
    TrackSpec(SHORT, "단기", 0.03, 0.02, 12, "4h"),
    TrackSpec(MID, "중기", 0.05, 0.03, 24, "4h"),
    TrackSpec(LONG, "장기", 0.10, 0.07, 168, "4h", require_above_cloud=True),
)
TRACK_BY_KEY = {t.key: t for t in TRACKS}

# BR26: 적중률 하한. 기존 레짐 트랙의 45%는 실측 능력(36.3%)보다 높아 "표본에서 우연히 높게
# 나온 코인"만 통과시켰다(워크포워드 실측: 표시 45% vs 실제 38.9%). 사용자 지시로 25~30%대에
# 맞춘다. 트랙 실측 도달률이 24~36%이므로 25%로 둔다.
MIN_HIT_RATE = 0.25

# BR26 보조지표: **BTC 4시간봉이 구름 위 + 해당 종목 RSI >= 50**.
#
# 최초 측정에서 "일봉도 구름 위"가 가장 효과적으로 보였으나(장기 +0.20% -> +0.72%) **룩어헤드였다**
# -- 아직 마감되지 않은 당일 일봉의 종가로 그날 진입을 판정했다. 마감 시각 기준으로 다시 재면
# 일봉 조건은 전 트랙에서 **해롭다**(초단기 -0.23% / 단기 -0.13% / 중기 -0.01% / 장기 +0.04%).
# 그래서 일봉 조건은 넣지 않는다.
#
# 마감 시각 기준 실측 기대수익 (조건 없음 -> RSI>=50 + BTC구름위):
#   초단기 -0.15% -> -0.05% / 단기 -0.06% -> +0.04% / 중기 +0.01% -> +0.07% / 장기 +0.20% -> +0.40%
# ADX>25는 오히려 해로웠고(초단기 -0.05%p), 기준선 상승·양운도 중립~음수여서 넣지 않는다.
# RSI 문턱은 사용자 지정 50이다(실측상 55가 근소 우위지만 지정값을 따른다).
RSI_MIN = 50.0

# 수집 대상 타임프레임. 1m/3m/5m은 제외한다 -- 20종 9년 기준 23GB를 쓰는데 초단기 기여가
# 창마다 부호가 갈렸다(90일 창 +2.5%p, 365일 창 -4.5%p). 1m은 BR22 가격 감시가 저장 없이
# 실시간 조회하므로 여기 없어도 알림 정밀도는 그대로다.
COLLECTED_TIMEFRAMES = ("15m", "30m", "1h", "4h", "1d", "1w", "1M")

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
    """보유 기간을 **판정 봉** 수로 환산."""
    return max(1, round(spec.hold_hours / TIMEFRAME_HOURS[spec.sim_timeframe]))


@dataclass(frozen=True)
class EntryContext:
    """BR26 보조지표 조회용. 시계열은 (시각, 값)의 오름차순 목록이며 이진탐색으로 조회한다 --
    선형 탐색을 진입 후보마다 돌리면 종목당 수만 봉 × 수천 진입이 되어 실행 시간이 폭증한다."""

    btc_cloud: list[tuple[datetime, bool]]
    rsi: list[float | None]


def _as_of(series: list[tuple[datetime, bool]], moment: datetime) -> bool:
    """`moment` 이전에 마감된 가장 최근 값. 이력보다 이르면 False -- 모르면 진입하지 않는다."""
    if not series:
        return False
    index = bisect_right([t for t, _ in series], moment) - 1
    return series[index][1] if index >= 0 else False


def aux_ok(context: EntryContext | None, candles: list[Candle], i: int) -> bool:
    """BR26: BTC 4시간봉이 구름 위 + 해당 종목 RSI >= 50.

    조회는 반드시 **마감 시각** 기준이다 -- 시가 시각으로 조회하면 아직 마감되지 않은 봉의 종가를
    쓰게 되어 룩어헤드가 된다. 최초 구현에서 실제로 이 실수를 했고 보조지표 효과가 3~4배로
    부풀어 보였다.

    context가 없으면 통과시킨다 -- 보조지표를 계산할 수 없는 호출(테스트 등)에서 조건이 조용히
    막히는 것보다 명시적으로 꺼진 편이 낫다."""
    if context is None:
        return True
    if not _as_of(context.btc_cloud, close_time(candles[i])):
        return False
    value = context.rsi[i] if i < len(context.rsi) else None
    return value is not None and value >= RSI_MIN


def entry_ok(points: list[IchimokuPoint], i: int, spec: TrackSpec) -> bool:
    """BR27: 트랙의 진입 조건 = 골든크로스 (+ 장기는 구름 위).

    "구름대도 참고하고 골든크로스인지 검증한다"는 요청을 트랙별 실측으로 나눈 결과다:

    | 트랙 | 골든크로스 단독 | + 구름 위 |
    |---|---|---|
    | 초단기 | +0.15% | +0.12% |
    | 단기 | +0.22% | +0.24% |
    | 중기 | +0.26% | +0.26% |
    | 장기 | +0.56% | **+1.06%** |

    보유가 길수록 구름(장기 추세)이 의미를 갖고, 8시간짜리 초단기에는 오히려 방해가 된다."""
    if not golden_cross(points, i):
        return False
    return above_cloud(points[i]) if spec.require_above_cloud else True


def golden_cross(points: list[IchimokuPoint], i: int) -> bool:
    """BR27: 전환선이 기준선을 아래에서 위로 교차한 봉.

    구름 돌파를 대신해 채택했다 -- 전 트랙에서 기대수익이 더 높다(초단기 +0.15% vs +0.07%,
    단기 +0.22% vs +0.10%, 중기 +0.26% vs +0.11%, 장기 +0.56% vs +0.40%).

    도달률이 아니라 기대수익으로 골랐다는 점이 중요하다 -- 기존 `entry_signal`은 도달률 42.0%로
    가장 높았지만 기대수익은 +0.02%였다. 타임아웃 청산의 손익이 결과를 좌우한다."""
    if i <= 0 or i >= len(points):
        return False
    point, previous = points[i], points[i - 1]
    if None in (point.tenkan, point.kijun, previous.tenkan, previous.kijun):
        return False
    return point.tenkan > point.kijun and previous.tenkan <= previous.kijun


@dataclass(frozen=True)
class SimSeries:
    """BR27: 판정 전용 봉. 진입봉과 다른 해상도이므로 시각으로 정렬해 찾는다."""

    candles: list[Candle]
    close_times: list[datetime]

    @classmethod
    def build(cls, candles: list[Candle]) -> "SimSeries":
        return cls(candles=candles, close_times=[close_time(c) for c in candles])

    def index_at(self, moment: datetime) -> int:
        """`moment` 시점에 이미 마감된 마지막 판정봉. 없으면 -1."""
        return bisect_right(self.close_times, moment) - 1


def simulate(
    entry_candles: list[Candle], i: int, spec: TrackSpec, sim: SimSeries
) -> tuple[str, float, datetime] | None:
    """목표/손절 중 먼저 닿는 쪽을 **판정봉 해상도**로 가린다. 보유 창이 안 차면 판정 불가(None).

    판정봉을 진입봉과 분리한 이유: 8시간 보유를 4시간봉으로 재면 봉이 2개뿐이라, 한 봉에서
    목표·손절이 겹칠 때 손절로 간주하는 보수적 규칙이 과하게 작동해 **손실 쪽으로 편향**된다.
    실측상 판정만 30분봉으로 바꿔도 초단기 기대수익이 -0.03% -> +0.07%가 됐다.

    데이터 끝에서 잘라 타임아웃으로 세지 않는다 -- 진행 중인 매매가 표본에 섞인다(BR24 결함).

    반환값의 세 번째는 **청산 시각**이다. 겹침 제거를 시각으로 해야 진입봉과 판정봉의 격자가
    달라도 어긋나지 않는다."""
    entry = entry_candles[i].close
    if entry <= 0:
        return None
    start = sim.index_at(close_time(entry_candles[i]))
    bars = bars_for(spec)
    if start < 0 or start + bars >= len(sim.candles):
        return None
    target, stop = entry * (1 + spec.target), entry * (1 - spec.stop)
    for j in range(start + 1, start + 1 + bars):
        if sim.candles[j].low <= stop:
            return "loss", -spec.stop, sim.close_times[j]
        if sim.candles[j].high >= target:
            return "win", spec.target, sim.close_times[j]
    last = start + bars
    return "timeout", sim.candles[last].close / entry - 1, sim.close_times[last]


def compute_track_stats(
    entry_candles: list[Candle],
    points: list[IchimokuPoint],
    spec: TrackSpec,
    sim: SimSeries,
    context: EntryContext | None = None,
):
    """해당 코인 이력에서 같은 조건으로 진입했던 과거 시점의 성적.

    보유 중에는 새 진입을 잡지 않는다(겹침 제거) -- 겹치는 진입을 각각 세면 같은 구간이 여러 번
    반영되어 표본이 부풀고 확률이 왜곡된다. 진입봉과 판정봉의 격자가 다르므로 **시각**으로 겹침을
    판정한다."""
    wins = losses = timeouts = 0
    returns: list[float] = []
    drawdowns: list[float] = []
    last_exit: datetime | None = None
    for i in range(len(points)):
        if not entry_ok(points, i, spec):
            continue
        moment = close_time(entry_candles[i])
        if last_exit is not None and moment < last_exit:
            continue
        if not aux_ok(context, entry_candles, i):
            continue
        simulated = simulate(entry_candles, i, spec, sim)
        if simulated is None:
            continue
        result, ret, exit_at = simulated
        entry = entry_candles[i].close
        start, end = sim.index_at(moment), sim.index_at(exit_at)
        drawdowns.append(min((sim.candles[j].low / entry - 1) for j in range(start + 1, end + 1)))
        last_exit = exit_at
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


def latest_entry(
    candles: list[Candle],
    points: list[IchimokuPoint],
    spec: TrackSpec,
    context: EntryContext | None = None,
) -> int | None:
    """가장 최근 마감봉이 골든크로스이고 보조지표까지 통과하면 그 인덱스."""
    if not points:
        return None
    i = len(points) - 1
    if not entry_ok(points, i, spec) or not aux_ok(context, candles, i):
        return None
    return i


def entry_time_of(candles: list[Candle], i: int):
    return close_time(candles[i])
