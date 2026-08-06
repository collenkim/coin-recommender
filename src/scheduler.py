import logging

from apscheduler.schedulers.background import BackgroundScheduler
from apscheduler.triggers.cron import CronTrigger
from fastapi import FastAPI

from src.config import settings
from src.pipeline import AlreadyRunningError, run_recommendation_pipeline

logger = logging.getLogger(__name__)

_JOB_ID = "recommendation_pipeline"


def _run_job() -> None:
    try:
        run_recommendation_pipeline()
    except AlreadyRunningError:
        logger.info("Scheduled run skipped: a pipeline run is already in progress")
    except Exception:
        logger.error("Scheduled pipeline run failed", exc_info=True)


def start_scheduler(app: FastAPI) -> BackgroundScheduler:
    """FR12: hourly, 5 minutes past the hour (waits for the 1h candle to close).
    coalesce+misfire_grace_time avoid piling up missed runs after downtime (NFR Design)."""
    scheduler = BackgroundScheduler()
    scheduler.add_job(
        _run_job,
        trigger=CronTrigger(minute=5),
        id=_JOB_ID,
        coalesce=True,
        misfire_grace_time=settings.scheduler_misfire_grace_seconds,
    )
    scheduler.start()
    app.state.scheduler = scheduler
    return scheduler


def stop_scheduler(app: FastAPI) -> None:
    scheduler = getattr(app.state, "scheduler", None)
    if scheduler is not None:
        scheduler.shutdown(wait=False)
