import logging
from contextlib import asynccontextmanager
from datetime import datetime, timedelta, timezone

from fastapi import FastAPI, HTTPException
from fastapi.responses import JSONResponse
from pydantic import BaseModel

from src.backtest import FORWARD_BARS_1H, STOP_LOSS, TARGET_RETURN, wilson_lower
from src.long_track import LONG_HOLD_BARS_4H, LONG_STOP_LOSS, LONG_TARGET_RETURN
from src.config import settings
from src.data_store import DataStore
from src.pipeline import AlreadyRunningError, run_recommendation_pipeline
from src.scheduler import start_scheduler, stop_scheduler
from src.scorer import check_market_phase

logger = logging.getLogger(__name__)

# BR17: the service predicts a move within one day, so a recommendation stops being actionable once
# its 24h window has elapsed -- the same horizon the backtest measures over.
_VALIDITY_WINDOW = timedelta(hours=FORWARD_BARS_1H)


class RecommendationOut(BaseModel):
    market: str
    source: str = "binance"
    expected_return: float
    n: int
    hit_count: int
    # BR21: 손절가를 치기 전에 목표가에 도달한 과거 비율과 그 95% 신뢰 하한. 표본이 얇은 코인의
    # "적중률 100%"를 그대로 확률처럼 읽지 않도록 하한을 함께 노출한다.
    hit_rate: float | None = None
    hit_rate_lower: float | None = None
    # BR16/BR18 entry guide. entry_price/entry_time are the bar the backtest measures from;
    # target_price/stop_price/exit_deadline are derived so they cannot drift out of step.
    entry_time: datetime | None = None
    entry_price: float | None = None
    target_price: float | None = None
    stop_price: float | None = None
    exit_deadline: datetime | None = None
    max_drawdown: float | None = None
    target_reached: bool | None = None
    realized_return: float | None = None
    track: str = "short"  # BR24: "short" | "long"


class RunSummary(BaseModel):
    run_time: datetime | None
    regime_bullish: bool
    recommendations: list[RecommendationOut]


class AssetMomentumOut(BaseModel):
    market: str
    label: str  # strong_bull | weak_bull | not_bull
    returns: dict[str, float]  # 1d / 7d / 30d / 90d / 365d


class MarketPhaseOut(BaseModel):
    """BR23: 표시 전용 시장 국면. `regime_bullish`(진입 게이트)와는 별개 기준이므로 둘이
    어긋날 수 있다 -- 게이트는 BTC 30일 단독, 국면은 BTC/ETH 5구간이다."""

    phase: str  # strong_bull | weak_bull | not_bull
    assets: list[AssetMomentumOut]


class RecommendationsResponse(RunSummary):
    expired: bool = False
    history: list[RunSummary] | None = None
    # 현재 시각 기준 국면이므로 과거 회차(history)에는 붙이지 않는다 -- 붙이면 지난 회차가
    # 그때의 국면이었던 것처럼 읽힌다.
    market_phase: MarketPhaseOut | None = None


class HealthResponse(BaseModel):
    status: str
    db_connected: bool


@asynccontextmanager
async def lifespan(app: FastAPI):
    start_scheduler(app)
    yield
    stop_scheduler(app)


app = FastAPI(title="coin-recommender", lifespan=lifespan)


@app.exception_handler(Exception)
async def global_exception_handler(request, exc: Exception):
    logger.error("Unhandled exception", exc_info=exc)
    return JSONResponse(status_code=500, content={"detail": "internal error"})


_LONG_VALIDITY_WINDOW = timedelta(hours=LONG_HOLD_BARS_4H * 4)


def _to_recommendation_out(r) -> RecommendationOut:
    entry_time = getattr(r, "entry_time", None)
    entry_price = getattr(r, "entry_price", None)
    track = getattr(r, "track", "short")
    # BR24: 트랙마다 목표·손절·보유기간이 다르다. 단기 상수를 공유하면 장기 추천의
    # target_price/stop_price/exit_deadline이 전부 틀린 값으로 나간다.
    target, stop, window = (
        (LONG_TARGET_RETURN, LONG_STOP_LOSS, _LONG_VALIDITY_WINDOW)
        if track == "long"
        else (TARGET_RETURN, STOP_LOSS, _VALIDITY_WINDOW)
    )
    # 적중률은 저장된 n/hit_count에서 그대로 유도한다 -- 별도 컬럼을 두면 저장 시점과 계산 방식이
    # 어긋날 수 있고, 과거 회차 행에도 같은 규칙이 자동으로 적용된다.
    hit_rate = (r.hit_count / r.n) if r.n else None
    return RecommendationOut(
        market=r.market,
        source=getattr(r, "source", "binance"),
        expected_return=r.expected_return,
        n=r.n,
        hit_count=r.hit_count,
        hit_rate=hit_rate,
        hit_rate_lower=None if hit_rate is None else wilson_lower(r.hit_count, r.n),
        entry_time=entry_time,
        entry_price=entry_price,
        target_price=None if entry_price is None else entry_price * (1 + target),
        stop_price=None if entry_price is None else entry_price * (1 - stop),
        exit_deadline=None if entry_time is None else entry_time + window,
        max_drawdown=getattr(r, "max_drawdown", None),
        target_reached=getattr(r, "target_reached", None),
        realized_return=getattr(r, "realized_return", None),
        track=track,
    )


def _to_market_phase_out(phase) -> MarketPhaseOut | None:
    if phase is None:
        return None
    return MarketPhaseOut(
        phase=phase.phase,
        assets=[AssetMomentumOut(market=a.market, label=a.label, returns=a.returns) for a in phase.assets],
    )


def _to_run_summary(run) -> RunSummary:
    return RunSummary(
        run_time=run.run_time,
        regime_bullish=run.regime_bullish,
        recommendations=[_to_recommendation_out(r) for r in run.recommendations],
    )


def _is_expired(run_time: datetime | None, now: datetime) -> bool:
    """BR17: every recommendation in a run shares its hour, so run-level expiry is enough and it also
    covers legacy rows that predate entry_time."""
    return run_time is not None and now > run_time + _VALIDITY_WINDOW


@app.get("/recommendations", response_model=RecommendationsResponse)
def get_recommendations(limit: int = 1) -> RecommendationsResponse:
    """BR10: limit<=1 (default) preserves the pre-existing response shape; limit>1 additionally
    populates `history` with the most recent `limit` runs.

    BR17: once the latest run is older than the 24h horizon it is reported with an empty
    `recommendations` list and `expired: true` -- serving a day-old entry price as if it were
    actionable is worse than reporting nothing. `history` is left intact, since it is explicitly a
    record of past runs rather than something to act on."""
    store = DataStore(settings.db_path)
    now = datetime.now(timezone.utc)
    # BR23: 저장된 회차 값이 아니라 지금 캔들에서 계산한다 -- 국면은 회차의 속성이 아니라
    # 현재 시장의 속성이고, 그래서 DB 스키마도 건드리지 않는다.
    phase = _to_market_phase_out(check_market_phase(store))

    if limit <= 1:
        latest = store.get_latest_run()
        if latest is None:
            return RecommendationsResponse(
                run_time=None, regime_bullish=False, recommendations=[], market_phase=phase
            )
        summary = _to_run_summary(latest)
        if _is_expired(latest.run_time, now):
            return RecommendationsResponse(
                run_time=summary.run_time,
                regime_bullish=summary.regime_bullish,
                recommendations=[],
                expired=True,
                market_phase=phase,
            )
        return RecommendationsResponse(**summary.model_dump(), market_phase=phase)

    runs = store.get_recent_runs(limit=limit)
    if not runs:
        return RecommendationsResponse(
            run_time=None, regime_bullish=False, recommendations=[], history=[], market_phase=phase
        )
    history = [_to_run_summary(r) for r in runs]
    expired = _is_expired(runs[0].run_time, now)
    latest_recommendations = [] if expired else history[0].recommendations
    return RecommendationsResponse(
        run_time=history[0].run_time,
        regime_bullish=history[0].regime_bullish,
        recommendations=latest_recommendations,
        expired=expired,
        history=history,
        market_phase=phase,
    )


@app.post("/run", response_model=RecommendationsResponse)
def trigger_run() -> RecommendationsResponse:
    try:
        result = run_recommendation_pipeline()
    except AlreadyRunningError:
        raise HTTPException(status_code=409, detail="이미 실행 중입니다")
    return RecommendationsResponse(
        run_time=result.run_time,
        regime_bullish=result.regime is not None,
        recommendations=[
            _to_recommendation_out(r) for r in result.recommendations + (result.long_recommendations or [])
        ],
        market_phase=_to_market_phase_out(result.phase),
    )


@app.get("/health", response_model=HealthResponse)
def health() -> HealthResponse | JSONResponse:
    try:
        store = DataStore(settings.db_path)
        store.ping()
        return HealthResponse(status="ok", db_connected=True)
    except Exception:
        logger.error("Health check failed", exc_info=True)
        return JSONResponse(status_code=500, content={"status": "error", "db_connected": False})
