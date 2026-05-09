import logging

import pytz
from apscheduler.schedulers.asyncio import AsyncIOScheduler
from apscheduler.triggers.cron import CronTrigger

from app.core.config import settings

logger = logging.getLogger(__name__)
_scheduler = AsyncIOScheduler()


def start() -> None:
    tz = pytz.timezone(settings.timezone)
    _scheduler.add_job(
        _run_weekly_report,
        CronTrigger(day_of_week="mon", hour=9, minute=0, timezone=tz),
        id="weekly_report",
        replace_existing=True,
    )
    _scheduler.add_job(
        _run_monthly_report,
        CronTrigger(day=1, hour=7, minute=0, timezone=tz),
        id="monthly_report",
        replace_existing=True,
    )
    _scheduler.start()
    logger.info(
        "Scheduler started — weekly report: Monday 09:00 %s | monthly report: day 1 07:00 %s",
        settings.timezone, settings.timezone,
    )


def stop() -> None:
    if _scheduler.running:
        _scheduler.shutdown(wait=False)


async def _run_weekly_report() -> None:
    from app.db.repositories import report_repo
    from app.services import report_service, whatsapp_service

    logger.info("Running scheduled weekly report → sending to Oberdan private")
    try:
        report_text, saved = await report_service.generate_report(trigger="weekly")
        await whatsapp_service.send_private_message(settings.oberdan_phone, report_text)
        if saved:
            report_repo.mark_sent(saved["id"])
    except Exception:
        logger.exception("Failed to run scheduled weekly report")


async def _run_monthly_report() -> None:
    from app.db.repositories import report_repo
    from app.services import report_service, whatsapp_service

    logger.info("Running scheduled monthly report")
    try:
        report_text, saved = await report_service.generate_report(trigger="scheduled")
        await whatsapp_service.send_group_message(report_text)
        if saved:
            report_repo.mark_sent(saved["id"])
    except Exception:
        logger.exception("Failed to run scheduled monthly report")
