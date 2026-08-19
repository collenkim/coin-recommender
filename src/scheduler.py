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
    """BR31: 30분마다 (매시 5분/35분). 봉 마감 직후 5분을 두고 도는 것은 그대로다.

    **주기를 줄여도 진입 검출이 빨라지지는 않는다** -- 진입 신호는 4시간봉이 마감돼야 생기고,
    마감 후 5분이면 이미 최단 지연이다. 30분 주기의 실효는 (1) 파이프라인이 실패하거나 지연됐을
    때 다음 시도까지의 공백이 절반으로 줄고, (2) 30분·1시간봉 수집이 더 촘촘해지는 것이다.
    같은 진입봉이 반복 검출되는 문제는 BR31 중복 억제가 담당한다.

    coalesce+misfire_grace_time avoid piling up missed runs after downtime (NFR Design).

    BR22: 가격 감시는 5분마다 따로 돈다. 활성 추천이 없으면 조회 없이 즉시 끝나므로
    추천이 없는 동안의 비용은 사실상 없다."""
    scheduler = BackgroundScheduler()
    scheduler.add_job(
        _run_job,
        trigger=CronTrigger(minute="5,35"),
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
