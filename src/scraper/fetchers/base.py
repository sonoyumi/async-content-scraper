from __future__ import annotations

from abc import ABC, abstractmethod


class FetchError(Exception):
    pass


class RobotsDisallowed(FetchError):
    pass


class Fetcher(ABC):
    @abstractmethod
    async def fetch(self, url: str, **kwargs) -> str:
        """Return raw HTML content for the given URL."""
