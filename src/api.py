import logging
from contextlib import asynccontextmanager
from datetime import datetime, timedelta, timezone

from fastapi import FastAPI, HTTPException
from fastapi.responses import JSONResponse
from pydantic import BaseModel

from src.backtest import FORWARD_BARS_1H
from src.config import settings
from src.data_store import DataStore
from src.pipeline import AlreadyRunningError, run_recommendation_pipeline
from src.scheduler import start_scheduler, stop_scheduler
from src.scorer import EXPECTED_RETURN_THRESHOLD

logger = logging.getLogger(__name__)

# BR17: the service predicts a move within one day, so a recommendation stops being actionable once
# its 24h window has elapsed -- the same horizon the backtest measures over.
_VALIDITY_WINDOW = timedelta(hours=FORWARD_BARS_1H)


class RecommendationOut(BaseModel):
    market: str
    source: str = "upbit"
    expected_return: float
    n: int
    hit_count: int
    # BR16 entry guide. entry_price/entry_time are the bar the backtest measures from; target_price
    # and exit_deadline are derived from them so they cannot drift out of step.
    entry_time: datetime | None = None
    entry_price: float | None = None
    target_price: float | None = None
    exit_deadline: datetime | None = None
    max_drawdown: float | None = None
    target_reached: bool | None = None
    realized_return: float | None = None


class RunSummary(BaseModel):
    run_time: datetime | None
    regime_bullish: bool
    recommendations: list[RecommendationOut]


class RecommendationsResponse(RunSummary):
    expired: bool = False
    history: list[RunSummary] | None = None


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


def _to_recommendation_out(r) -> RecommendationOut:
    entry_time = getattr(r, "entry_time", None)
    entry_price = getattr(r, "entry_price", None)
    return RecommendationOut(
        market=r.market,
        source=getattr(r, "source", "upbit"),
        expected_return=r.expected_return,
        n=r.n,
        hit_count=r.hit_count,
        entry_time=entry_time,
        entry_price=entry_price,
        target_price=None if entry_price is None else entry_price * (1 + EXPECTED_RETURN_THRESHOLD),
        exit_deadline=None if entry_time is None else entry_time + _VALIDITY_WINDOW,
        max_drawdown=getattr(r, "max_drawdown", None),
        target_reached=getattr(r, "target_reached", None),
        realized_return=getattr(r, "realized_return", None),
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

    if limit <= 1:
        latest = store.get_latest_run()
        if latest is None:
            return RecommendationsResponse(run_time=None, regime_bullish=False, recommendations=[])
        summary = _to_run_summary(latest)
        if _is_expired(latest.run_time, now):
            return RecommendationsResponse(
                run_time=summary.run_time, regime_bullish=summary.regime_bullish, recommendations=[], expired=True
            )
        return RecommendationsResponse(**summary.model_dump())

    runs = store.get_recent_runs(limit=limit)
    if not runs:
        return RecommendationsResponse(run_time=None, regime_bullish=False, recommendations=[], history=[])
    history = [_to_run_summary(r) for r in runs]
    expired = _is_expired(runs[0].run_time, now)
    latest_recommendations = [] if expired else history[0].recommendations
    return RecommendationsResponse(
        run_time=history[0].run_time,
        regime_bullish=history[0].regime_bullish,
        recommendations=latest_recommendations,
        expired=expired,
        history=history,
    )


@app.post("/run", response_model=RecommendationsResponse)
def trigger_run() -> RecommendationsResponse:
    try:
        result = run_recommendation_pipeline()
    except AlreadyRunningError:
        raise HTTPException(status_code=409, detail="이미 실행 중입니다")
    return RecommendationsResponse(
        run_time=result.run_time,
        regime_bullish=result.regime_bullish,
        recommendations=[_to_recommendation_out(r) for r in result.recommendations],
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
