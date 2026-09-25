from __future__ import annotations

import datetime as dt

from scraper.dedup.hasher import ExtractedItem
from scraper.extractors.base import Extractor
from scraper.logging_config import get_logger

logger = get_logger(component="telegram_extractor")


class TelegramExtractor(Extractor):
    """Demo placeholder.

    The private/production version of this class parses the public
    web-preview markup at ``t.me/s/<channel>`` (message text, media,
    forwarded-from labels, view counts, media-group grouping, per-type
    handling for photos/videos/documents, defensive per-message error
    handling, etc.) into ``ExtractedItem`` objects that flow through the
    same fetch -> extract -> dedup -> store -> notify pipeline as the HTML
    extractor.

    That concrete parsing logic is intentionally not included in this public
    repository -- see the disclaimer in README.md. What *is* fully shown
    here is the surrounding architecture it plugs into: the ``Extractor``
    interface, the fetch pipeline, the DB-level deduplication, the
    concurrency/rate-limiting layer, and the scheduler -- all of which this
    class would use identically to ``HtmlExtractor``.

    If you're evaluating this repo: swap this stub for your own
    implementation of ``extract()`` following the same contract as
    ``HtmlExtractor`` (never raise on a single malformed item -- log and
    skip it, see extractors/base.py), and everything else in the pipeline
    works unchanged.
    """

    def extract(self, raw_html: str, *, base_url: str) -> list[ExtractedItem]:
        logger.info(
            "telegram_extractor_stub_called",
            base_url=base_url,
            note="public demo build -- extraction logic removed, see class docstring",
        )
        raise NotImplementedError(
            "TelegramExtractor.extract() is a demo stub in the public build. "
            "The production implementation parses t.me/s/<channel> preview "
            "markup; it was intentionally left out of this repository. "
            "See the class docstring and README.md for context."
        )

    # Kept so the type/shape of a real implementation is visible without
    # exposing the actual parsing rules.
    def _extract_date(self, message) -> dt.datetime | None:  # pragma: no cover
        raise NotImplementedError

    def _extract_media(self, message) -> list[dict]:  # pragma: no cover
        raise NotImplementedError

    def _extract_meta(self, message) -> dict:  # pragma: no cover
        raise NotImplementedError
