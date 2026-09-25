from __future__ import annotations

import datetime as dt

from sqlalchemy import (
    BigInteger,
    Boolean,
    DateTime,
    ForeignKey,
    Integer,
    String,
    Text,
    UniqueConstraint,
)
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.orm import DeclarativeBase, Mapped, mapped_column, relationship
from sqlalchemy.types import JSON

JSONType = JSON().with_variant(JSONB, "postgresql")

# SQLite only auto-increments a column declared as exactly "INTEGER PRIMARY
# KEY" (its rowid alias); a bare BIGINT primary key silently does *not* get
# autoincrement, so ON CONFLICT ... RETURNING id would insert a NULL id and
# violate the NOT NULL constraint. Use BIGINT only on Postgres, where it
# behaves as expected.
BigIntPk = Integer().with_variant(BigInteger(), "postgresql")


class Base(DeclarativeBase):
    pass


def utcnow() -> dt.datetime:
    return dt.datetime.now(dt.UTC)


class Source(Base):
    __tablename__ = "sources"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    name: Mapped[str] = mapped_column(String(255), nullable=False)
    type: Mapped[str] = mapped_column(String(20), nullable=False)
    url: Mapped[str] = mapped_column(String(2048), nullable=False)
    enabled: Mapped[bool] = mapped_column(Boolean, nullable=False, default=True)
    poll_interval_sec: Mapped[int] = mapped_column(Integer, nullable=False, default=900)
    config: Mapped[dict] = mapped_column(JSONType, nullable=False, default=dict)
    respect_robots: Mapped[bool] = mapped_column(Boolean, nullable=False, default=True)
    download_media: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False)

    last_polled_at: Mapped[dt.datetime | None] = mapped_column(DateTime(timezone=True))
    last_success_at: Mapped[dt.datetime | None] = mapped_column(DateTime(timezone=True))
    consecutive_errors: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    last_error: Mapped[str | None] = mapped_column(Text)

    created_at: Mapped[dt.datetime] = mapped_column(DateTime(timezone=True), default=utcnow)
    updated_at: Mapped[dt.datetime] = mapped_column(
        DateTime(timezone=True), default=utcnow, onupdate=utcnow
    )

    posts: Mapped[list[Post]] = relationship(back_populates="source", cascade="all, delete-orphan")

    __table_args__ = (UniqueConstraint("name", "url", name="uq_sources_name_url"),)


class Post(Base):
    __tablename__ = "posts"

    id: Mapped[int] = mapped_column(BigIntPk, primary_key=True)
    source_id: Mapped[int] = mapped_column(ForeignKey("sources.id", ondelete="CASCADE"), nullable=False)
    external_id: Mapped[str] = mapped_column(String(255), nullable=False)
    content_hash: Mapped[str] = mapped_column(String(64), nullable=False)
    text: Mapped[str | None] = mapped_column(Text)
    published_at: Mapped[dt.datetime | None] = mapped_column(DateTime(timezone=True))
    fetched_at: Mapped[dt.datetime] = mapped_column(DateTime(timezone=True), default=utcnow)
    url: Mapped[str | None] = mapped_column(String(2048))
    media: Mapped[list] = mapped_column(JSONType, nullable=False, default=list)
    notified_at: Mapped[dt.datetime | None] = mapped_column(DateTime(timezone=True))
    raw_meta: Mapped[dict] = mapped_column(JSONType, nullable=False, default=dict)

    source: Mapped[Source] = relationship(back_populates="posts")

    __table_args__ = (
        UniqueConstraint("source_id", "external_id", name="uq_posts_source_external_id"),
        UniqueConstraint("source_id", "content_hash", name="uq_posts_source_content_hash"),
    )


class PollLog(Base):
    __tablename__ = "poll_log"

    id: Mapped[int] = mapped_column(BigIntPk, primary_key=True)
    source_id: Mapped[int] = mapped_column(ForeignKey("sources.id", ondelete="CASCADE"), nullable=False)
    started_at: Mapped[dt.datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    finished_at: Mapped[dt.datetime | None] = mapped_column(DateTime(timezone=True))
    status: Mapped[str] = mapped_column(String(20), nullable=False)
    new_items: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    error_message: Mapped[str | None] = mapped_column(Text)
