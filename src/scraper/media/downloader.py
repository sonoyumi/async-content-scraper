from __future__ import annotations

import hashlib
from pathlib import Path
from urllib.parse import urlparse

import httpx

from scraper.logging_config import get_logger
from scraper.settings import settings

logger = get_logger(component="media_downloader")

_MAX_FILE_SIZE_BYTES = 50 * 1024 * 1024  # 50 MB safety cap


def _guess_filename(url: str) -> str:
    name = Path(urlparse(url).path).name
    if name:
        return name
    return hashlib.sha256(url.encode("utf-8")).hexdigest()[:16]


async def download_media(url: str, source_id: int, post_external_id: str) -> str | None:
    directory = Path(settings.media_dir) / str(source_id) / post_external_id
    directory.mkdir(parents=True, exist_ok=True)
    destination = directory / _guess_filename(url)

    try:
        async with httpx.AsyncClient(timeout=30, follow_redirects=True) as client:
            async with client.stream("GET", url) as response:
                response.raise_for_status()
                size = 0
                with destination.open("wb") as fh:
                    async for chunk in response.aiter_bytes():
                        size += len(chunk)
                        if size > _MAX_FILE_SIZE_BYTES:
                            logger.warning("media_download_too_large", url=url)
                            destination.unlink(missing_ok=True)
                            return None
                        fh.write(chunk)
        return str(destination)
    except httpx.HTTPError:
        logger.exception("media_download_failed", url=url)
        destination.unlink(missing_ok=True)
        return None
