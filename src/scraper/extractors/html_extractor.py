from __future__ import annotations

import datetime as dt
from urllib.parse import urljoin

from bs4 import BeautifulSoup
from dateutil import parser as dateutil_parser

from scraper.dedup.hasher import ExtractedItem, compute_content_hash
from scraper.extractors.base import Extractor
from scraper.logging_config import get_logger
from scraper.sources.schemas import HtmlConfig

logger = get_logger(component="html_extractor")


def _parse_date(raw: str | None, date_format: str | None) -> dt.datetime | None:
    if not raw:
        return None
    try:
        if date_format:
            parsed = dt.datetime.strptime(raw, date_format)
        else:
            parsed = dateutil_parser.parse(raw)
        if parsed.tzinfo is None:
            parsed = parsed.replace(tzinfo=dt.UTC)
        return parsed
    except (ValueError, OverflowError):
        logger.warning("date_parse_failed", raw=raw)
        return None


class HtmlExtractor(Extractor):
    def __init__(self, config: HtmlConfig):
        self.config = config

    def extract(self, raw_html: str, *, base_url: str) -> list[ExtractedItem]:
        try:
            soup = BeautifulSoup(raw_html, "html.parser")
            elements = soup.select(self.config.list_selector)
        except Exception:  # noqa: BLE001
            logger.exception("list_selector_failed", selector=self.config.list_selector)
            return []

        items: list[ExtractedItem] = []
        for element in elements:
            try:
                item = self._extract_one(element, base_url=base_url)
                if item is not None:
                    items.append(item)
            except Exception:  # noqa: BLE001
                logger.exception("item_extraction_failed")
        return items

    def _extract_one(self, element, *, base_url: str) -> ExtractedItem | None:
        sel = self.config.item_selectors

        text_parts = []
        if sel.title:
            title_el = element.select_one(sel.title)
            if title_el:
                text_parts.append(title_el.get_text(separator=" ", strip=True))
        if sel.text:
            text_el = element.select_one(sel.text)
            if text_el:
                text_parts.append(text_el.get_text(separator="\n", strip=True))
        text = "\n\n".join(part for part in text_parts if part) or None

        raw_date = None
        if sel.date:
            date_el = element.select_one(sel.date)
            if date_el:
                raw_date = date_el.get(sel.date_attr) if sel.date_attr else date_el.get_text(strip=True)
        published_at = _parse_date(raw_date, self.config.date_format)

        url = None
        if sel.link:
            link_el = element.select_one(sel.link)
            if link_el and link_el.get(sel.link_attr):
                url = urljoin(base_url, link_el[sel.link_attr])

        media: list[dict] = []
        if sel.media:
            for media_el in element.select(sel.media):
                media_url = media_el.get(sel.media_attr)
                if media_url:
                    media.append({"type": "image", "url": urljoin(base_url, media_url)})

        if not text and not url and not media:
            return None

        media_urls = [m["url"] for m in media]
        content_hash = compute_content_hash(text, media_urls)
        external_id = url or content_hash

        return ExtractedItem(
            external_id=external_id,
            text=text,
            published_at=published_at,
            url=url,
            media=media,
            content_hash=content_hash,
        )
