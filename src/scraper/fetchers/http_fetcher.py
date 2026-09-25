from __future__ import annotations

import asyncio

import httpx
from tenacity import (
    retry,
    retry_if_exception_type,
    stop_after_attempt,
    wait_exponential,
)

from scraper.fetchers.base import Fetcher, FetchError, RobotsDisallowed
from scraper.fetchers.robots import can_fetch
from scraper.settings import settings


class HttpFetcher(Fetcher):
    def __init__(self, user_agent: str | None = None, timeout: float = 20.0):
        self.user_agent = user_agent or settings.user_agent
        self.timeout = timeout

    @retry(
        stop=stop_after_attempt(3),
        wait=wait_exponential(multiplier=1, min=2, max=30),
        retry=retry_if_exception_type((httpx.TransportError, httpx.TimeoutException)),
        reraise=True,
    )
    async def _get(self, url: str) -> httpx.Response:
        async with httpx.AsyncClient(
            headers={"User-Agent": self.user_agent},
            timeout=httpx.Timeout(connect=10, read=self.timeout, write=10, pool=10),
            follow_redirects=True,
        ) as client:
            response = await client.get(url)
            response.raise_for_status()
            return response

    async def fetch(self, url: str, *, respect_robots: bool = True, **kwargs) -> str:
        if respect_robots:
            allowed = await asyncio.to_thread(can_fetch, url, self.user_agent)
            if not allowed:
                raise RobotsDisallowed(f"robots.txt disallows fetching {url}")

        try:
            response = await self._get(url)
        except httpx.HTTPError as exc:
            raise FetchError(str(exc)) from exc

        return response.text
