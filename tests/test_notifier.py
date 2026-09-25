import datetime as dt

import httpx
import respx

from scraper.notifier.telegram_bot import TelegramNotifier
from scraper.storage.models import Post


def _post(idx: int) -> Post:
    return Post(
        id=idx,
        source_id=1,
        external_id=str(idx),
        content_hash="x" * 64,
        text=f"post number {idx}",
        published_at=dt.datetime.now(dt.UTC),
        url=f"https://example.com/{idx}",
        media=[],
        raw_meta={},
    )


async def test_send_digest_posts_one_message():
    notifier = TelegramNotifier(bot_token="TEST", chat_id="123")

    with respx.mock:
        route = respx.post("https://api.telegram.org/botTEST/sendMessage").mock(
            return_value=httpx.Response(200, json={"ok": True})
        )
        await notifier.send_digest("Test source", [_post(1), _post(2)])

    assert route.called
    sent_text = route.calls.last.request.content.decode()
    assert "post number 1" in sent_text
    assert "post number 2" in sent_text


async def test_send_digest_respects_retry_after():
    notifier = TelegramNotifier(bot_token="TEST", chat_id="123")

    with respx.mock:
        route = respx.post("https://api.telegram.org/botTEST/sendMessage").mock(
            side_effect=[
                httpx.Response(429, json={"parameters": {"retry_after": 0}}),
                httpx.Response(200, json={"ok": True}),
            ]
        )
        await notifier.send_digest("Test source", [_post(1)])

    assert route.call_count == 2


async def test_send_digest_noop_without_posts():
    notifier = TelegramNotifier(bot_token="TEST", chat_id="123")
    with respx.mock:
        route = respx.post("https://api.telegram.org/botTEST/sendMessage")
        await notifier.send_digest("Test source", [])
    assert not route.called
