"""APScheduler: one daily job that snapshots the cumulative meters (SPEC 6).

In-memory scheduler (the job is re-registered on every startup, so no persistent
job store is needed). The job opens its own DB session and does a sync HA read.
"""
import logging

from apscheduler.schedulers.background import BackgroundScheduler

from ..db import SessionLocal
from . import ha, snapshot

log = logging.getLogger("ohm_assistant.scheduler")
_scheduler: BackgroundScheduler | None = None


def _daily_snapshot_job() -> None:
    if not ha.has_token():
        return
    try:
        with SessionLocal() as db:
            res = snapshot.take_snapshot(db)
        log.info("daily snapshot: stored=%s skipped=%s", res["stored"], res["skipped"])
    except Exception:  # never let a scheduler job crash the loop
        log.exception("daily snapshot failed")


def init() -> None:
    global _scheduler
    if _scheduler is not None:
        return
    _scheduler = BackgroundScheduler(timezone="UTC")
    # Just after midnight; energy counters are stable overnight.
    _scheduler.add_job(_daily_snapshot_job, "cron", hour=0, minute=5,
                       id="daily_snapshot", replace_existing=True)
    _scheduler.start()
    log.info("scheduler started (daily snapshot 00:05 UTC)")


def shutdown() -> None:
    global _scheduler
    if _scheduler is not None:
        _scheduler.shutdown(wait=False)
        _scheduler = None
