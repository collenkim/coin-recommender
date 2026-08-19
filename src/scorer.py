from dataclasses import dataclass
from datetime import datetime

from src.backtest import (
    MIN_HIT_RATE,
    MIN_SIGNAL_SAMPLES,
    build_regime_series,
    compute_signal_stats,
    entry_signal,
    wilson_lower,
)
from src.data_store import DataStore, close_time
from src.features import above_cloud, compute_ichimoku, compute_rsi
from src.market_phase import OPEN_PHASES, MarketPhase, current_phase
from src.tracks import (
    MIN_HIT_RATE as TRACK_MIN_HIT_RATE,
    TRACKS,
    EntryContext,
    SimSeries,
    TrackSpec,
    compute_track_stats,
    entry_ok,
    latest_entry,
)

SOURCE = "binance"
BTC_MARKET = "BTCUSDT"
ETH_MARKET = "ETHUSDT"
REGIME_TIMEFRAME = "4h"
# 문구 판정에 쓰는 자산. 추천 후보에서는 제외돼 있지만(BR8) 시장 국면의 기준으로는 수집한다.
PHASE_MARKETS = (BTC_MARKET, ETH_MARKET)


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
    # BR25: 기존 레짐 게이트 트랙(BR18~BR21)은 "regime"으로 구분한다. BR25의 "short"(단기)와
    # 목표·손절이 같지만 보유가 24시간 vs 12시간으로 달라, 같은 키를 쓰면 감시가 12시간 만에
    # 끊긴다.
    track: str = "regime"


def _regime_series(data_store: DataStore) -> list[tuple[datetime, str | None]]:
    return build_regime_series(data_store.get_candles(SOURCE, BTC_MARKET, REGIME_TIMEFRAME))


def check_market_regime(data_store: DataStore) -> str | None:
    """BR20: 지금이 강한 상승장인지 반등 상승장인지, 둘 다 아니면 None.

    BTC 4시간봉 수집이 실패해 이력이 없으면 None -- 레짐을 알 수 없을 때 진입하지 않는 쪽이
    안전하다 (Unit 1 BR7의 graceful degradation과 같은 방향)."""
    series = _regime_series(data_store)
    return series[-1][1] if series else None


def check_market_phase(data_store: DataStore) -> MarketPhase | None:
    """BR23: BTC/ETH 5구간 모멘텀으로 본 현재 국면 (표시 전용, 진입 여부와 무관).

    `check_market_regime`과 나란히 두되 서로 호출하지 않는다 -- 문구가 게이트에 영향을 주는 경로를
    아예 만들지 않기 위해서다."""
    return current_phase(
        {market: data_store.get_candles(SOURCE, market, REGIME_TIMEFRAME) for market in PHASE_MARKETS}
    )


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


def _btc_cloud_series(data_store: DataStore) -> list[tuple[datetime, bool]]:
    """BR26: BTC 4시간봉 구름 위 여부 시계열. 봉 시각이 아니라 **마감 시각**에 붙인다 --
    시가 시각을 쓰면 아직 모르는 종가로 판정하는 룩어헤드가 된다(BR20에서 겪은 것과 같은 함정)."""
    candles = data_store.get_candles(SOURCE, BTC_MARKET, REGIME_TIMEFRAME)
    return [(close_time(c), above_cloud(p)) for c, p in zip(candles, compute_ichimoku(candles))]


def _entry_context(data_store: DataStore, market: str, candles: list, btc_cloud) -> EntryContext:
    return EntryContext(btc_cloud=btc_cloud, rsi=compute_rsi(candles))


def _sim_series(data_store: DataStore, market: str, timeframe: str, cache: dict | None) -> SimSeries:
    """BR27 판정봉. 네 트랙이 같은 판정봉(30분)을 쓰므로 캐시가 없으면 네 번 다시 만든다."""
    key = ("sim", market, timeframe)
    if cache is not None and key in cache:
        return cache[key]
    value = SimSeries.build(data_store.get_candles(SOURCE, market, timeframe))
    if cache is not None:
        cache[key] = value
    return value


def _candles_and_points(data_store: DataStore, market: str, timeframe: str, cache: dict | None):
    """일목 계산은 봉 수에 비례해 비싸다. 네 트랙이 모두 4시간봉 진입이라 캐시가 없으면
    같은 종목의 같은 봉을 네 번 계산한다."""
    key = (market, timeframe)
    if cache is not None and key in cache:
        return cache[key]
    candles = data_store.get_candles(SOURCE, market, timeframe)
    value = (candles, compute_ichimoku(candles))
    if cache is not None:
        cache[key] = value
    return value


def generate_track_recommendations(
    candidates: list[str],
    data_store: DataStore,
    spec: TrackSpec,
    btc_cloud=None,
    candle_cache=None,
) -> list[Recommendation]:
    """BR25: 한 트랙의 추천. 진입 타임프레임의 가장 최근 마감봉이 구름대 돌파면 후보가 되고,
    같은 조건의 과거 성적이 표본 하한을 넘으면 추천이 된다.

    BR26/BR32: 적중률 하한은 트랙별이다(단타 25% / 중기 20% / 장기 15%). 문턱이 실측 능력보다
    높으면 "우연히 높게 나온 코인"만 통과시킨다 -- 기존 레짐 트랙의 45% 문턱(실측 36.3%)이 그랬다.
    정렬은 Wilson 하한으로 한다."""
    if btc_cloud is None:
        btc_cloud = _btc_cloud_series(data_store)
    recommendations = []
    for market in candidates:
        candles, points = _candles_and_points(data_store, market, spec.timeframe, candle_cache)
        if not points or not entry_ok(points, len(points) - 1, spec):
            # 최신봉이 골든크로스가 아니면 RSI·판정봉을 만들 이유가 없다. 대부분의 종목이 여기서
            # 걸러지므로 이 순서가 실행 시간을 좌우한다.
            continue
        context = _entry_context(data_store, market, candles, btc_cloud)
        index = latest_entry(candles, points, spec, context)
        if index is None:
            continue

        sim = _sim_series(data_store, market, spec.sim_timeframe, candle_cache)
        stats = compute_track_stats(candles, points, spec, sim, context)
        if stats["n"] < spec.min_samples or stats["hit_rate"] is None:
            continue
        if stats["hit_rate"] < spec.min_hit_rate:
            continue

        entry_candle = candles[index]
        recommendations.append(
            Recommendation(
                market=market,
                n=stats["n"],
                hit_count=stats["hit_count"],
                hit_rate=stats["hit_rate"],
                hit_rate_lower=wilson_lower(stats["hit_count"], stats["n"]),
                expected_return=stats["expected_return"],
                entry_time=close_time(entry_candle),
                entry_price=entry_candle.close,
                max_drawdown=stats["max_drawdown"],
                track=spec.key,
            )
        )
    return sorted(recommendations, key=lambda r: r.hit_rate_lower, reverse=True)


def generate_all_tracks(
    candidates: list[str], data_store: DataStore, phase: MarketPhase | None, limit: int
) -> dict[str, list[Recommendation]]:
    """BR25: 국면 게이트를 한 번 확인하고 4개 트랙을 각각 산출한다.

    게이트는 약상승장까지 연다 -- 실측상 약상승장 구간은 기대수익이 양수였고 '상승장 아님'
    구간은 0 또는 음수였다."""
    if phase is None or phase.phase not in OPEN_PHASES:
        return {spec.key: [] for spec in TRACKS}
    btc_cloud = _btc_cloud_series(data_store)
    candle_cache: dict = {}
    return {
        spec.key: generate_track_recommendations(candidates, data_store, spec, btc_cloud, candle_cache)[:limit]
        for spec in TRACKS
    }
