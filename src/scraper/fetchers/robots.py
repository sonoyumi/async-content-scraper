from __future__ import annotations

import time
import urllib.robotparser
from urllib.parse import urlparse

import httpx

_CACHE: dict[str, tuple[float, urllib.robotparser.RobotFileParser]] = {}
_CACHE_TTL_SEC = 24 * 3600


def _robots_url(url: str) -> str:
    parsed = urlparse(url)
    return f"{parsed.scheme}://{parsed.netloc}/robots.txt"


def can_fetch(url: str, user_agent: str) -> bool:
    robots_url = _robots_url(url)
    now = time.monotonic()

    cached = _CACHE.get(robots_url)
    if cached and now - cached[0] < _CACHE_TTL_SEC:
        parser = cached[1]
    else:
        parser = urllib.robotparser.RobotFileParser()
        parser.set_url(robots_url)
        try:
            response = httpx.get(robots_url, timeout=10, follow_redirects=True)
            if response.status_code == 200:
                parser.parse(response.text.splitlines())
            else:
                # No robots.txt or inaccessible: treat as allow-all.
                parser.parse([])
        except httpx.HTTPError:
            parser.parse([])
        _CACHE[robots_url] = (now, parser)

    return parser.can_fetch(user_agent, url)
