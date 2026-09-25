from __future__ import annotations

from abc import ABC, abstractmethod

from scraper.dedup.hasher import ExtractedItem


class Extractor(ABC):
    @abstractmethod
    def extract(self, raw_html: str, *, base_url: str) -> list[ExtractedItem]:
        """Parse raw HTML into a list of extracted items. Must never raise on
        malformed/unexpected markup — log and return [] instead, so a single
        broken source doesn't take down the whole poll cycle."""
