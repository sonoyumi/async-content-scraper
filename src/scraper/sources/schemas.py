from __future__ import annotations

from typing import Literal

from pydantic import BaseModel, Field, model_validator


class ItemSelectors(BaseModel):
    title: str | None = None
    text: str | None = None
    date: str | None = None
    date_attr: str | None = None
    link: str | None = None
    link_attr: str = "href"
    media: str | None = None
    media_attr: str = "src"


class HtmlConfig(BaseModel):
    list_selector: str
    item_selectors: ItemSelectors
    pagination: str | None = None
    date_format: str | None = None


class PlaywrightConfig(HtmlConfig):
    wait_for_selector: str | None = None
    scroll_iterations: int = 0
    scroll_pause_ms: int = 800


class TelegramConfig(BaseModel):
    channel: str
    max_pages: int = 1


CONFIG_MODELS: dict[str, type[HtmlConfig] | type[PlaywrightConfig] | type[TelegramConfig]] = {
    "html": HtmlConfig,
    "playwright": PlaywrightConfig,
    "telegram": TelegramConfig,
}


class SourceEntry(BaseModel):
    name: str
    type: Literal["html", "playwright", "telegram"]
    url: str
    enabled: bool = True
    poll_interval_sec: int = 900
    respect_robots: bool = True
    download_media: bool = False
    config: HtmlConfig | PlaywrightConfig | TelegramConfig | dict = Field(default_factory=dict)

    @model_validator(mode="after")
    def _parse_config(self) -> SourceEntry:
        if isinstance(self.config, dict):
            model = CONFIG_MODELS[self.type]
            self.config = model.model_validate(self.config)
        return self


class SourcesFile(BaseModel):
    sources: list[SourceEntry]
