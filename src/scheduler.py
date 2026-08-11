import logging

from apscheduler.schedulers.background import BackgroundScheduler
from apscheduler.triggers.cron import CronTrigger
from fastapi import FastAPI

from src.config import settings
from src.pipeline import AlreadyRunningError, run_price_monitor, run_recommendation_pipeline

logger = logging.getLogger(__name__)

_JOB_ID = "recommendation_pipeline"
_MONITOR_JOB_ID = "price_monitor"


def _run_job() -> None:
    try:
        run_recommendation_pipeline()
    except AlreadyRunningError:
        logger.info("Scheduled run skipped: a pipeline run is already in progress")
    except Exception:
        logger.error("Scheduled pipeline run failed", exc_info=True)


def _run_monitor_job() -> None:
    try:
        events = run_price_monitor()
        if events:
            logger.info("Price monitor raised %d event(s)", len(events))
    except Exception:
        logger.error("Scheduled price monitor run failed", exc_info=True)


def start_scheduler(app: FastAPI) -> BackgroundScheduler:
    """FR12: hourly, 5 minutes past the hour (waits for the 1h candle to close).
    coalesce+misfire_grace_time avoid piling up missed runs after downtime (NFR Design).

    BR22: 가격 감시는 5분마다 따로 돈다. 활성 추천이 없으면 조회 없이 즉시 끝나므로
    추천이 없는 동안의 비용은 사실상 없다."""
    scheduler = BackgroundScheduler()
    scheduler.add_job(
        _run_job,
        trigger=CronTrigger(minute=5),
        id=_JOB_ID,
        coalesce=True,
        misfire_grace_time=settings.scheduler_misfire_grace_seconds,
    )
    scheduler.add_job(
        _run_monitor_job,
        trigger=CronTrigger(minute="*/5"),
        id=_MONITOR_JOB_ID,
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
