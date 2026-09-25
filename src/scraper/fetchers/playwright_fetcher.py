from __future__ import annotations

import asyncio

from scraper.fetchers.base import Fetcher, FetchError
from scraper.settings import settings

_playwright_ctx = None
_browser = None
_browser_lock = asyncio.Lock()


async def _get_browser():
    """Lazily starts one shared Chromium instance and reuses it across every
    fetch/source. The previous version launched a brand-new browser process
    per single fetch (async with async_playwright() as pw: ... browser =
    await pw.chromium.launch(...)), which is multi-second startup cost paid
    on every poll cycle for every Playwright source -- expensive and, under
    concurrent polling, a source of flakiness. max_concurrent_playwright
    already caps how many pages run at once, so one persistent browser is
    safe; a crashed/closed browser is detected and relaunched automatically."""
    global _playwright_ctx, _browser

    async with _browser_lock:
        if _browser is not None and _browser.is_connected():
            return _browser

        from playwright.async_api import async_playwright

        if _playwright_ctx is None:
            _playwright_ctx = await async_playwright().start()
        _browser = await _playwright_ctx.chromium.launch(headless=True)
        return _browser


async def close_browser() -> None:
    """Releases the shared Chromium process. Call this during graceful
    shutdown (see scheduler/runner.py) so `scraper run` doesn't leave an
    orphaned chromium process behind on SIGTERM/SIGINT."""
    global _playwright_ctx, _browser

    async with _browser_lock:
        if _browser is not None:
            await _browser.close()
            _browser = None
        if _playwright_ctx is not None:
            await _playwright_ctx.stop()
            _playwright_ctx = None


class PlaywrightFetcher(Fetcher):
    """Fetches JS-heavy pages via the shared headless Chromium instance.
    Requires `playwright install chromium`."""

    def __init__(self, user_agent: str | None = None):
        self.user_agent = user_agent or settings.user_agent

    async def fetch(
        self,
        url: str,
        *,
        wait_for_selector: str | None = None,
        scroll_iterations: int = 0,
        scroll_pause_ms: int = 800,
        timeout_ms: int = 30000,
        **kwargs,
    ) -> str:
        try:
            browser = await _get_browser()
        except ImportError as exc:  # pragma: no cover
            raise FetchError("playwright is not installed") from exc

        page = None
        try:
            page = await browser.new_page(user_agent=self.user_agent)
            await page.goto(url, wait_until="networkidle", timeout=timeout_ms)

            if wait_for_selector:
                await page.wait_for_selector(wait_for_selector, timeout=timeout_ms)

            for _ in range(scroll_iterations):
                await page.mouse.wheel(0, 10000)
                await page.wait_for_timeout(scroll_pause_ms)

            return await page.content()
        except Exception as exc:  # noqa: BLE001
            raise FetchError(f"playwright fetch failed for {url}: {exc}") from exc
        finally:
            if page is not None:
                await page.close()
