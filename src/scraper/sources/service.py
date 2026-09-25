from __future__ import annotations

from scraper.extractors.base import Extractor
from scraper.extractors.html_extractor import HtmlExtractor
from scraper.extractors.telegram_extractor import TelegramExtractor
from scraper.fetchers.base import Fetcher
from scraper.fetchers.http_fetcher import HttpFetcher
from scraper.fetchers.playwright_fetcher import PlaywrightFetcher
from scraper.sources.schemas import HtmlConfig, PlaywrightConfig, TelegramConfig
from scraper.storage.models import Source

_CONFIG_MODELS: dict[str, type[HtmlConfig] | type[PlaywrightConfig] | type[TelegramConfig]] = {
    "html": HtmlConfig,
    "playwright": PlaywrightConfig,
    "telegram": TelegramConfig,
}


def parse_source_config(source: Source):
    model = _CONFIG_MODELS[source.type]
    return model.model_validate(source.config)


def build_fetcher(source: Source) -> Fetcher:
    if source.type == "playwright":
        return PlaywrightFetcher()
    return HttpFetcher()


def build_extractor(source: Source) -> Extractor:
    config = parse_source_config(source)
    if source.type == "telegram":
        return TelegramExtractor()
    return HtmlExtractor(config)


def fetch_kwargs(source: Source) -> dict:
    config = parse_source_config(source)
    if source.type == "playwright":
        return {
            "respect_robots": source.respect_robots,
            "wait_for_selector": config.wait_for_selector,
            "scroll_iterations": config.scroll_iterations,
            "scroll_pause_ms": config.scroll_pause_ms,
        }
    return {"respect_robots": source.respect_robots}
