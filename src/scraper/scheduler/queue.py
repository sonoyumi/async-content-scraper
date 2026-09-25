from __future__ import annotations

import asyncio
from contextlib import asynccontextmanager
from urllib.parse import urlparse

from aiolimiter import AsyncLimiter

from scraper.settings import settings

_domain_limiters: dict[str, AsyncLimiter] = {}

_http_semaphore = asyncio.Semaphore(settings.max_concurrent_fetches)
_playwright_semaphore = asyncio.Semaphore(settings.max_concurrent_playwright)


def _domain_limiter(url: str) -> AsyncLimiter:
    domain = urlparse(url).netloc
    if domain not in _domain_limiters:
        # At most 1 request every 2 seconds per domain, so dozens of
        # independently-scheduled sources on the same domain (e.g. t.me)
        # can't collectively hammer it just because their intervals happen
        # to line up.
        _domain_limiters[domain] = AsyncLimiter(1, 2)
    return _domain_limiters[domain]


@asynccontextmanager
async def fetch_slot(url: str, *, is_playwright: bool):
    semaphore = _playwright_semaphore if is_playwright else _http_semaphore
    limiter = _domain_limiter(url)
    async with semaphore:
        async with limiter:
            yield
