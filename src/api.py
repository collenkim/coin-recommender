import logging
from contextlib import asynccontextmanager
from datetime import datetime

from fastapi import FastAPI, HTTPException
from fastapi.responses import JSONResponse
from pydantic import BaseModel

from src.config import settings
from src.data_store import DataStore
from src.pipeline import AlreadyRunningError, run_recommendation_pipeline
from src.scheduler import start_scheduler, stop_scheduler

logger = logging.getLogger(__name__)


class RecommendationOut(BaseModel):
    market: str
    source: str = "upbit"
    expected_return: float
    n: int
    hit_count: int
    target_reached: bool | None = None
    realized_return: float | None = None


class RunSummary(BaseModel):
    run_time: datetime | None
    regime_bullish: bool
    recommendations: list[RecommendationOut]


class RecommendationsResponse(RunSummary):
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
    return RecommendationOut(
        market=r.market,
        source=getattr(r, "source", "upbit"),
        expected_return=r.expected_return,
        n=r.n,
        hit_count=r.hit_count,
        target_reached=r.target_reached,
        realized_return=r.realized_return,
    )


def _to_run_summary(run) -> RunSummary:
    return RunSummary(
        run_time=run.run_time,
        regime_bullish=run.regime_bullish,
        recommendations=[_to_recommendation_out(r) for r in run.recommendations],
    )


@app.get("/recommendations", response_model=RecommendationsResponse)
def get_recommendations(limit: int = 1) -> RecommendationsResponse:
    """BR10: limit<=1 (default) preserves the exact pre-existing response shape (backward compatible);
    limit>1 additionally populates `history` with the most recent `limit` runs."""
    store = DataStore(settings.db_path)

    if limit <= 1:
        latest = store.get_latest_run()
        if latest is None:
            return RecommendationsResponse(run_time=None, regime_bullish=False, recommendations=[])
        summary = _to_run_summary(latest)
        return RecommendationsResponse(**summary.model_dump())

    runs = store.get_recent_runs(limit=limit)
    if not runs:
        return RecommendationsResponse(run_time=None, regime_bullish=False, recommendations=[], history=[])
    history = [_to_run_summary(r) for r in runs]
    return RecommendationsResponse(**history[0].model_dump(), history=history)


@app.post("/run", response_model=RecommendationsResponse)
def trigger_run() -> RecommendationsResponse:
    try:
        result = run_recommendation_pipeline()
    except AlreadyRunningError:
        raise HTTPException(status_code=409, detail="이미 실행 중입니다")
    return RecommendationsResponse(
        run_time=result.run_time,
        regime_bullish=result.regime_bullish,
        recommendations=[
            RecommendationOut(market=r.market, source=r.source, expected_return=r.expected_return, n=r.n, hit_count=r.hit_count)
            for r in result.recommendations
        ],
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
