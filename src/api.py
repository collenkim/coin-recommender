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
    expected_return: float
    n: int
    hit_count: int


class RecommendationsResponse(BaseModel):
    run_time: datetime | None
    regime_bullish: bool
    recommendations: list[RecommendationOut]


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


@app.get("/recommendations", response_model=RecommendationsResponse)
def get_recommendations() -> RecommendationsResponse:
    store = DataStore(settings.db_path)
    latest = store.get_latest_run()
    if latest is None:
        return RecommendationsResponse(run_time=None, regime_bullish=False, recommendations=[])
    return RecommendationsResponse(
        run_time=latest.run_time,
        regime_bullish=latest.regime_bullish,
        recommendations=[
            RecommendationOut(market=r.market, expected_return=r.expected_return, n=r.n, hit_count=r.hit_count)
            for r in latest.recommendations
        ],
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
        recommendations=[
            RecommendationOut(market=r.market, expected_return=r.expected_return, n=r.n, hit_count=r.hit_count)
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
