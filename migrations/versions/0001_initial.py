"""initial schema

Revision ID: 0001
Revises:
Create Date: 2026-09-23

"""
import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

revision = "0001"
down_revision = None
branch_labels = None
depends_on = None


def upgrade() -> None:
    json_type = sa.JSON().with_variant(postgresql.JSONB(), "postgresql")

    op.create_table(
        "sources",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("name", sa.String(length=255), nullable=False),
        sa.Column("type", sa.String(length=20), nullable=False),
        sa.Column("url", sa.String(length=2048), nullable=False),
        sa.Column("enabled", sa.Boolean(), nullable=False, server_default=sa.true()),
        sa.Column("poll_interval_sec", sa.Integer(), nullable=False, server_default="900"),
        sa.Column("config", json_type, nullable=False),
        sa.Column("respect_robots", sa.Boolean(), nullable=False, server_default=sa.true()),
        sa.Column("download_media", sa.Boolean(), nullable=False, server_default=sa.false()),
        sa.Column("last_polled_at", sa.DateTime(timezone=True)),
        sa.Column("last_success_at", sa.DateTime(timezone=True)),
        sa.Column("consecutive_errors", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("last_error", sa.Text()),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
        sa.UniqueConstraint("name", "url", name="uq_sources_name_url"),
    )

    op.create_table(
        "posts",
        sa.Column("id", sa.BigInteger(), primary_key=True),
        sa.Column(
            "source_id",
            sa.Integer(),
            sa.ForeignKey("sources.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column("external_id", sa.String(length=255), nullable=False),
        sa.Column("content_hash", sa.String(length=64), nullable=False),
        sa.Column("text", sa.Text()),
        sa.Column("published_at", sa.DateTime(timezone=True)),
        sa.Column("fetched_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("url", sa.String(length=2048)),
        sa.Column("media", json_type, nullable=False),
        sa.Column("notified_at", sa.DateTime(timezone=True)),
        sa.Column("raw_meta", json_type, nullable=False),
        sa.UniqueConstraint("source_id", "external_id", name="uq_posts_source_external_id"),
        sa.UniqueConstraint("source_id", "content_hash", name="uq_posts_source_content_hash"),
    )
    op.create_index("ix_posts_source_fetched", "posts", ["source_id", "fetched_at"])
    op.create_index(
        "ix_posts_notified_null",
        "posts",
        ["notified_at"],
        postgresql_where=sa.text("notified_at IS NULL"),
    )

    op.create_table(
        "poll_log",
        sa.Column("id", sa.BigInteger(), primary_key=True),
        sa.Column(
            "source_id",
            sa.Integer(),
            sa.ForeignKey("sources.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column("started_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("finished_at", sa.DateTime(timezone=True)),
        sa.Column("status", sa.String(length=20), nullable=False),
        sa.Column("new_items", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("error_message", sa.Text()),
    )
    op.create_index("ix_poll_log_source_started", "poll_log", ["source_id", "started_at"])


def downgrade() -> None:
    op.drop_table("poll_log")
    op.drop_index("ix_posts_notified_null", table_name="posts")
    op.drop_index("ix_posts_source_fetched", table_name="posts")
    op.drop_table("posts")
    op.drop_table("sources")
