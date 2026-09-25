import datetime as dt

from scraper.dedup.hasher import ExtractedItem
from scraper.storage.repository import (
    mark_notified,
    unnotified_posts,
    upsert_post,
    upsert_source,
)


def _item(external_id: str, text: str) -> ExtractedItem:
    return ExtractedItem(
        external_id=external_id,
        text=text,
        published_at=dt.datetime.now(dt.UTC),
        url=f"https://example.com/{external_id}",
    )


def test_upsert_post_ignores_duplicate_external_id(db_session):
    source = upsert_source(db_session, name="Test", type_="html", url="https://example.com", config={})
    db_session.commit()

    first = upsert_post(db_session, source.id, _item("1", "hello"))
    db_session.commit()
    assert first is not None

    duplicate = upsert_post(db_session, source.id, _item("1", "hello"))
    db_session.commit()
    assert duplicate is None


def test_unnotified_posts_and_mark_notified(db_session):
    source = upsert_source(db_session, name="Test2", type_="html", url="https://example2.com", config={})
    db_session.commit()

    post = upsert_post(db_session, source.id, _item("1", "hello"))
    db_session.commit()

    pending = unnotified_posts(db_session, source.id)
    assert [p.id for p in pending] == [post.id]

    mark_notified(db_session, [post.id])
    db_session.commit()

    assert unnotified_posts(db_session, source.id) == []
