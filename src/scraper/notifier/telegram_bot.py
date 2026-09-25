from __future__ import annotations

import asyncio

import httpx

from scraper.logging_config import get_logger
from scraper.settings import settings
from scraper.storage.models import Post

logger = get_logger(component="notifier")

_MAX_MESSAGE_LEN = 4000
_MAX_TEXT_PREVIEW = 500
_INTER_MESSAGE_DELAY_SEC = 1.0


def _format_post(post: Post) -> str:
    preview = (post.text or "").strip()
    if len(preview) > _MAX_TEXT_PREVIEW:
        preview = preview[:_MAX_TEXT_PREVIEW].rstrip() + "…"
    lines = [preview] if preview else []
    if post.url:
        lines.append(post.url)
    return "\n".join(lines) if lines else "(без текста)"


def _chunk_digest(source_name: str, posts: list[Post]) -> list[str]:
    header = f"🔔 {source_name} — новых постов: {len(posts)}\n\n"
    chunks: list[str] = []
    current = header
    for post in posts:
        entry = _format_post(post) + "\n\n"
        if len(current) + len(entry) > _MAX_MESSAGE_LEN:
            chunks.append(current.rstrip())
            current = ""
        current += entry
    if current.strip():
        chunks.append(current.rstrip())
    return chunks


class TelegramNotifier:
    def __init__(self, bot_token: str | None = None, chat_id: str | None = None):
        self.bot_token = bot_token or settings.notifier_bot_token
        self.chat_id = chat_id or settings.notifier_chat_id
        self._api_base = f"https://api.telegram.org/bot{self.bot_token}"

    async def _send_message(self, client: httpx.AsyncClient, text: str) -> None:
        while True:
            response = await client.post(
                f"{self._api_base}/sendMessage",
                json={"chat_id": self.chat_id, "text": text, "disable_web_page_preview": False},
            )
            if response.status_code == 429:
                retry_after = response.json().get("parameters", {}).get("retry_after", 5)
                logger.warning("telegram_rate_limited", retry_after=retry_after)
                await asyncio.sleep(retry_after)
                continue
            response.raise_for_status()
            return

    async def send_digest(self, source_name: str, posts: list[Post]) -> None:
        if not posts:
            return
        if not self.bot_token or not self.chat_id:
            logger.warning("notifier_not_configured", source=source_name)
            return

        chunks = _chunk_digest(source_name, posts)
        async with httpx.AsyncClient(timeout=15) as client:
            for chunk in chunks:
                # Let httpx.HTTPError propagate: the caller must not mark these
                # posts as notified if a chunk fails, so they're retried next cycle.
                await self._send_message(client, chunk)
                await asyncio.sleep(_INTER_MESSAGE_DELAY_SEC)
