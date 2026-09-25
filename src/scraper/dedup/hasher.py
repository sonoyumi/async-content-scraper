from __future__ import annotations

import datetime as dt
import hashlib
import re
from dataclasses import dataclass, field


def normalize_text(text: str | None) -> str:
    if not text:
        return ""
    return re.sub(r"\s+", " ", text).strip()


def compute_content_hash(text: str | None, media_urls: list[str]) -> str:
    normalized_text = normalize_text(text)
    normalized_media = sorted(url.strip() for url in media_urls if url)
    payload = normalized_text + "|" + "|".join(normalized_media)
    return hashlib.sha256(payload.encode("utf-8")).hexdigest()


@dataclass
class ExtractedItem:
    external_id: str
    text: str | None
    published_at: dt.datetime | None
    url: str | None
    media: list[dict] = field(default_factory=list)
    raw_meta: dict = field(default_factory=dict)
    content_hash: str = ""

    def __post_init__(self) -> None:
        if not self.content_hash:
            media_urls = [m.get("url", "") for m in self.media]
            self.content_hash = compute_content_hash(self.text, media_urls)
        if not self.external_id:
            self.external_id = self.content_hash
