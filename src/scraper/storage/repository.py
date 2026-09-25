from __future__ import annotations

import datetime as dt

from sqlalchemy import select, update
from sqlalchemy.orm import Session

from scraper.dedup.hasher import ExtractedItem
from scraper.storage.models import PollLog, Post, Source


def upsert_source(session: Session, *, name: str, type_: str, url: str, **kwargs) -> Source:
    existing = session.execute(
        select(Source).where(Source.name == name, Source.url == url)
    ).scalar_one_or_none()
    if existing:
        existing.type = type_
        for key, value in kwargs.items():
            setattr(existing, key, value)
        return existing

    source = Source(name=name, type=type_, url=url, **kwargs)
    session.add(source)
    session.flush()
    return source


def list_enabled_sources(session: Session) -> list[Source]:
    return list(session.execute(select(Source).where(Source.enabled.is_(True))).scalars())


def get_source(session: Session, source_id: int) -> Source | None:
    return session.get(Source, source_id)


def _insert_ignore(session: Session, values: dict) -> int | None:
    dialect = session.get_bind().dialect.name
    if dialect == "postgresql":
        from sqlalchemy.dialects.postgresql import insert as pg_insert

        stmt = (
            pg_insert(Post)
            .values(**values)
            .on_conflict_do_nothing(constraint="uq_posts_source_external_id")
            .returning(Post.id)
        )
    else:
        from sqlalchemy.dialects.sqlite import insert as sqlite_insert

        stmt = (
            sqlite_insert(Post)
            .values(**values)
            .on_conflict_do_nothing(index_elements=["source_id", "external_id"])
            .returning(Post.id)
        )
    result = session.execute(stmt)
    row = result.first()
    return row[0] if row else None


def upsert_post(session: Session, source_id: int, item: ExtractedItem) -> Post | None:
    """Insert a post if it's new for this source. Returns the Post if newly inserted, else None."""
    values = {
        "source_id": source_id,
        "external_id": item.external_id,
        "content_hash": item.content_hash,
        "text": item.text,
        "published_at": item.published_at,
        "url": item.url,
        "media": item.media,
        "raw_meta": item.raw_meta,
    }
    new_id = _insert_ignore(session, values)
    if new_id is None:
        return None
    session.flush()
    return session.get(Post, new_id)


def unnotified_posts(session: Session, source_id: int | None = None) -> list[Post]:
    stmt = select(Post).where(Post.notified_at.is_(None)).order_by(Post.fetched_at)
    if source_id is not None:
        stmt = stmt.where(Post.source_id == source_id)
    return list(session.execute(stmt).scalars())


def mark_notified(session: Session, post_ids: list[int]) -> None:
    if not post_ids:
        return
    now = dt.datetime.now(dt.UTC)
    session.execute(
        update(Post).where(Post.id.in_(post_ids)).values(notified_at=now)
    )


def record_poll_start(session: Session, source_id: int) -> PollLog:
    log = PollLog(source_id=source_id, started_at=dt.datetime.now(dt.UTC), status="running")
    session.add(log)
    session.flush()
    return log


def record_poll_finish(
    session: Session, log: PollLog, *, status: str, new_items: int = 0, error_message: str | None = None
) -> None:
    log.finished_at = dt.datetime.now(dt.UTC)
    log.status = status
    log.new_items = new_items
    log.error_message = error_message


def mark_source_success(session: Session, source: Source) -> None:
    now = dt.datetime.now(dt.UTC)
    source.last_polled_at = now
    source.last_success_at = now
    source.consecutive_errors = 0
    source.last_error = None


def mark_source_error(session: Session, source: Source, error: str) -> None:
    now = dt.datetime.now(dt.UTC)
    source.last_polled_at = now
    source.consecutive_errors += 1
    source.last_error = error
