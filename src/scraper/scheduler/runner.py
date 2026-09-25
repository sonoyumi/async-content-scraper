from __future__ import annotations

import asyncio
import datetime as dt
import signal
from pathlib import Path

from apscheduler.schedulers.asyncio import AsyncIOScheduler
from apscheduler.triggers.interval import IntervalTrigger

from scraper.fetchers.playwright_fetcher import close_browser
from scraper.logging_config import get_logger
from scraper.poller import poll_source
from scraper.settings import settings
from scraper.sources.loader import seed_sources_from_file
from scraper.storage.database import init_db, session_scope
from scraper.storage.repository import list_enabled_sources

logger = get_logger(component="scheduler")

_JOB_PREFIX = "poll-source-"


def _job_id(source_id: int) -> str:
    return f"{_JOB_PREFIX}{source_id}"


async def _run_poll_job(source_id: int) -> None:
    try:
        new_count = await poll_source(source_id)
        logger.info("poll_job_done", source_id=source_id, new_items=new_count)
    except Exception:  # noqa: BLE001
        logger.exception("poll_job_crashed", source_id=source_id)


def sync_jobs(scheduler: AsyncIOScheduler) -> None:
    """(Re-)registers a job per enabled source, adding new ones and removing
    jobs for sources that were disabled/deleted since the last sync. Safe to
    call repeatedly -- APScheduler replaces a job with the same id in place."""
    with session_scope() as session:
        sources = list_enabled_sources(session)
        source_ids = {source.id for source in sources}
        source_intervals = {source.id: source.poll_interval_sec for source in sources}

    for job in scheduler.get_jobs():
        if job.id.startswith(_JOB_PREFIX):
            job_source_id = int(job.id.removeprefix(_JOB_PREFIX))
            if job_source_id not in source_ids:
                job.remove()

    for source_id, interval in source_intervals.items():
        scheduler.add_job(
            _run_poll_job,
            trigger=IntervalTrigger(seconds=interval, jitter=max(1, int(interval * 0.1))),
            args=[source_id],
            id=_job_id(source_id),
            replace_existing=True,
            max_instances=1,
            coalesce=True,
        )

    logger.info("jobs_synced", count=len(source_intervals))


def _write_heartbeat() -> None:
    """Touches a file with the current UTC timestamp on every tick. A
    process-external healthcheck (systemd, Docker HEALTHCHECK, monit, ...)
    can alert if this file stops being updated -- see DEPLOY_GUIDE.md. This
    catches the "process is alive but the scheduler loop is wedged" failure
    mode that a plain `systemctl is-active` / PID check cannot."""
    path = Path(settings.heartbeat_file)
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(dt.datetime.now(dt.UTC).isoformat())


async def run_forever() -> None:
    init_db()
    with session_scope() as session:
        seed_sources_from_file(session, settings.sources_config_path)

    scheduler = AsyncIOScheduler()
    sync_jobs(scheduler)
    scheduler.add_job(
        sync_jobs,
        trigger=IntervalTrigger(hours=24),
        args=[scheduler],
        id="resync-jobs",
        replace_existing=True,
    )
    scheduler.add_job(
        _write_heartbeat,
        trigger=IntervalTrigger(seconds=60),
        id="heartbeat",
        replace_existing=True,
    )
    _write_heartbeat()
    scheduler.start()
    logger.info("scheduler_started")

    # Graceful shutdown: systemd/docker stop send SIGTERM, not SIGINT, and
    # asyncio only turns SIGINT into a catchable KeyboardInterrupt by
    # default. Without a SIGTERM handler, `systemctl stop` /
    # `docker stop` would just hard-kill the process once its default grace
    # period elapses -- possibly mid-DB-write.
    stop_event = asyncio.Event()
    loop = asyncio.get_running_loop()

    def _request_shutdown(received_signal: signal.Signals) -> None:
        logger.info("shutdown_signal_received", signal=received_signal.name)
        stop_event.set()

    for sig in (signal.SIGTERM, signal.SIGINT):
        try:
            loop.add_signal_handler(sig, _request_shutdown, sig)
        except NotImplementedError:  # pragma: no cover - not available on Windows
            pass

    try:
        await stop_event.wait()
    finally:
        logger.info("shutdown_started")
        scheduler.shutdown(wait=False)
        await close_browser()
        logger.info("shutdown_complete")
