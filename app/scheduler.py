import logging
from apscheduler.schedulers.background import BackgroundScheduler
from apscheduler.triggers.cron import CronTrigger
from app.config import (
    COLLECT_CRON_HOUR,
    COLLECT_CRON_MINUTE,
    REPORT_CRON_HOUR,
    REPORT_CRON_MINUTE,
    TIMEZONE,
)

logger = logging.getLogger(__name__)
scheduler = BackgroundScheduler(timezone=TIMEZONE)


def start_scheduler():
    scheduler.add_job(
        _collect_job,
        trigger=CronTrigger(hour=COLLECT_CRON_HOUR, minute=COLLECT_CRON_MINUTE),
        id="daily_collect",
        replace_existing=True,
        max_instances=1,
    )
    scheduler.add_job(
        _analyze_job,
        trigger=CronTrigger(hour=COLLECT_CRON_HOUR, minute=COLLECT_CRON_MINUTE + 10),
        id="daily_analyze",
        replace_existing=True,
        max_instances=1,
    )
    scheduler.add_job(
        _report_job,
        trigger=CronTrigger(hour=REPORT_CRON_HOUR, minute=REPORT_CRON_MINUTE),
        id="daily_report",
        replace_existing=True,
        max_instances=1,
    )
    scheduler.start()
    logger.info("Scheduler started")


def shutdown_scheduler():
    scheduler.shutdown(wait=False)


def _collect_job():
    from app.services.collector import run_collection

    logger.info("Scheduled collection starting...")
    results = run_collection()
    total_new = sum(r["new_articles"] for r in results)
    msg = f"Total new articles: {total_new}"
    errors = [r for r in results if r["status"] != "success"]
    if errors:
        msg += " | Errors: " + "; ".join(f"{e['source']}: {e['status']}" for e in errors)
    logger.info(f"Scheduled collection done: {msg}")


def _analyze_job():
    from app.services.content_fetcher import fill_article_contents
    from app.services.analyzer import run_analysis

    logger.info("Scheduled content fetch & analysis starting...")
    fill_article_contents(limit=30)
    run_analysis(limit=50)
    logger.info("Scheduled analysis done")


def _report_job():
    from app.services.reporter import generate_report
    from app.services.feishu import FeishuConfigError, push_report_to_feishu

    logger.info("Scheduled report generation starting...")
    report_id = generate_report()
    if report_id:
        logger.info(f"Scheduled report done: id={report_id}")
        try:
            from app.models.database import get_db

            db = get_db()
            row = db.execute("SELECT report_date FROM daily_reports WHERE id=?", (report_id,)).fetchone()
            db.close()
            if row:
                push_report_to_feishu(row["report_date"])
        except FeishuConfigError as e:
            logger.info("Feishu push skipped: %s", e)
        except Exception as e:
            logger.exception("Feishu push failed: %s", e)
    else:
        logger.info("Scheduled report skipped (already exists or no articles)")
