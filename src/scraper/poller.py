from __future__ import annotations

import asyncio
import datetime as dt

from sqlalchemy.orm.attributes import flag_modified

from scraper.fetchers.base import FetchError
from scraper.logging_config import get_logger
from scraper.media.downloader import download_media
from scraper.notifier.telegram_bot import TelegramNotifier
from scraper.scheduler.queue import fetch_slot
from scraper.settings import settings
from scraper.sources.service import build_extractor, build_fetcher, fetch_kwargs
from scraper.storage.database import session_scope
from scraper.storage.models import Post, Source
from scraper.storage.repository import (
    get_source,
    mark_notified,
    mark_source_error,
    mark_source_success,
    record_poll_finish,
    record_poll_start,
    unnotified_posts,
    upsert_post,
)

logger = get_logger(component="poller")


def _backoff_active(source: Source) -> bool:
    """A source that has been failing repeatedly is skipped for progressively
    longer stretches instead of being retried every single scheduled tick --
    this is what consecutive_errors_backoff_* in settings.py is for. It was
    previously defined but never read anywhere; a source stuck in an error
    loop (e.g. selectors broken after a site redesign, or the site itself is
    down) would otherwise be hit at its normal poll_interval_sec forever."""
    threshold = settings.consecutive_errors_backoff_threshold
    if source.consecutive_errors <= threshold or source.last_polled_at is None:
        return False

    excess = source.consecutive_errors - threshold
    multiplier = min(
        settings.consecutive_errors_backoff_multiplier**excess,
        settings.consecutive_errors_backoff_max_multiplier,
    )
    backoff_seconds = source.poll_interval_sec * multiplier
    next_allowed_at = source.last_polled_at + dt.timedelta(seconds=backoff_seconds)
    return dt.datetime.now(dt.UTC) < next_allowed_at


def _start_poll_cycle(source_id: int):
    """Sync DB work for the start of a cycle, run off the event loop via
    asyncio.to_thread. Returns None if the source no longer exists."""
    with session_scope() as session:
        source = get_source(session, source_id)
        if source is None:
            logger.warning("poll_source_not_found", source_id=source_id)
            return None

        backoff_active = _backoff_active(source)
        poll_log = record_poll_start(session, source_id)
        session.flush()

        return {
            "source_name": source.name,
            "source_url": source.url,
            "is_playwright": source.type == "playwright",
            "download_media_enabled": source.download_media or settings.download_media,
            "backoff_active": backoff_active,
            "poll_log_id": poll_log.id,
        }


def _require_source(session, source_id: int) -> Source:
    source = get_source(session, source_id)
    if source is None:
        raise LookupError(f"Source {source_id} no longer exists")
    return source


def _build_pipeline(source_id: int):
    with session_scope() as session:
        source = _require_source(session, source_id)
        fetcher = build_fetcher(source)
        extractor = build_extractor(source)
        kwargs = fetch_kwargs(source)
    return fetcher, extractor, kwargs


def _store_new_items(source_id: int, items) -> tuple[int, list[dict]]:
    """Upserts extracted items and marks the source successful. Returns the
    count of genuinely new posts plus, for each new post that has media, the
    (post_id, external_id, media list) needed to download it afterwards --
    outside of this (or any) DB transaction, see _download_pending_media."""
    with session_scope() as session:
        new_posts = []
        for item in items:
            post = upsert_post(session, source_id, item)
            if post is not None:
                new_posts.append(post)

        source = _require_source(session, source_id)
        mark_source_success(session, source)

        pending_media = [
            {"post_id": post.id, "external_id": post.external_id, "media": list(post.media)}
            for post in new_posts
            if post.media
        ]
        return len(new_posts), pending_media


def _persist_media_paths(updates: dict[int, list[dict]]) -> None:
    with session_scope() as session:
        for post_id, media in updates.items():
            post = session.get(Post, post_id)
            if post is None:
                continue
            post.media = media
            flag_modified(post, "media")


async def _download_pending_media(source_id: int, pending: list[dict]) -> None:
    """Downloads media for already-committed posts. Deliberately run OUTSIDE
    any DB session/transaction: media can be large and slow, and holding a
    connection open for that long previously risked exhausting the pool
    under concurrent 24/7 load, and meant a slow download blocked the same
    transaction that had just stored the post rows."""
    updates: dict[int, list[dict]] = {}
    for entry in pending:
        media_list = entry["media"]
        for media_item in media_list:
            path = await download_media(media_item["url"], source_id, entry["external_id"])
            if path:
                media_item["downloaded_path"] = path
        updates[entry["post_id"]] = media_list

    if updates:
        await asyncio.to_thread(_persist_media_paths, updates)


def _load_unnotified(source_id: int) -> list[Post]:
    with session_scope() as session:
        posts = unnotified_posts(session, source_id)
        session.expunge_all()  # detach: used after the session/transaction is closed
        return posts


def _mark_notified_ids(post_ids: list[int]) -> None:
    with session_scope() as session:
        mark_notified(session, post_ids)


async def _notify_new_posts(source_id: int, source_name: str) -> None:
    """Sends the digest OUTSIDE any DB session -- the previous version held a
    transaction open across the Telegram HTTP call(s), including the sleep
    on a 429 rate-limit response, which could pin a DB connection open for
    many seconds under load."""
    pending = await asyncio.to_thread(_load_unnotified, source_id)
    if not pending:
        return

    notifier = TelegramNotifier()
    try:
        await notifier.send_digest(source_name, pending)
    except Exception:  # noqa: BLE001
        # Not marked notified -> retried next cycle. See TelegramNotifier.send_digest.
        logger.exception("notify_failed", source=source_name)
        return

    await asyncio.to_thread(_mark_notified_ids, [p.id for p in pending])


def _finish_poll_cycle(source_id: int, poll_log_id: int, error: str | None, new_count: int) -> None:
    from scraper.storage.models import PollLog

    with session_scope() as session:
        source = get_source(session, source_id)
        poll_log = session.get(PollLog, poll_log_id)
        if source is None or poll_log is None:
            return
        if error:
            mark_source_error(session, source, error)
            record_poll_finish(session, poll_log, status="error", error_message=error)
        else:
            record_poll_finish(session, poll_log, status="success", new_items=new_count)


async def poll_source(source_id: int, *, notify: bool = True) -> int:
    """Runs one fetch->extract->dedup->notify cycle for a single source.
    Returns the number of newly stored posts. Never raises: failures are
    recorded on the source/poll_log rows so one bad source can't take down
    a scheduler loop covering many sources.

    All DB access goes through asyncio.to_thread: SQLAlchemy's sync Session
    is used here on purpose (see AUDIT_REPORT.md for why a full async-ORM
    migration wasn't done), but calling it directly from a coroutine would
    block the whole event loop -- including every other source's concurrent
    fetch -- for the duration of each query. to_thread moves that blocking
    work off the loop while keeping the sync SQLAlchemy code unchanged."""

    cycle = await asyncio.to_thread(_start_poll_cycle, source_id)
    if cycle is None:
        return 0
    if cycle["backoff_active"]:
        logger.debug("poll_source_backoff_skip", source=cycle["source_name"])
        return 0

    source_name = cycle["source_name"]
    new_count = 0
    error: str | None = None

    try:
        fetcher, extractor, kwargs = await asyncio.to_thread(_build_pipeline, source_id)

        async with fetch_slot(cycle["source_url"], is_playwright=cycle["is_playwright"]):
            raw_html = await fetcher.fetch(cycle["source_url"], **kwargs)
        items = extractor.extract(raw_html, base_url=cycle["source_url"])

        new_count, pending_media = await asyncio.to_thread(_store_new_items, source_id, items)

        if cycle["download_media_enabled"] and pending_media:
            await _download_pending_media(source_id, pending_media)

        if notify and new_count:
            await _notify_new_posts(source_id, source_name)

    except FetchError as exc:
        error = str(exc)
        logger.warning("poll_source_fetch_error", source=source_name, error=error)
    except Exception as exc:  # noqa: BLE001
        error = str(exc)
        logger.exception("poll_source_unexpected_error", source=source_name)

    await asyncio.to_thread(_finish_poll_cycle, source_id, cycle["poll_log_id"], error, new_count)
    return new_count
