from __future__ import annotations

from pathlib import Path

import yaml
from sqlalchemy.orm import Session

from scraper.logging_config import get_logger
from scraper.sources.schemas import SourcesFile
from scraper.storage.repository import upsert_source

logger = get_logger(component="sources_loader")


def load_sources_file(path: str | Path) -> SourcesFile:
    with open(path, encoding="utf-8") as fh:
        raw = yaml.safe_load(fh) or {}
    return SourcesFile.model_validate(raw)


def seed_sources_from_file(session: Session, path: str | Path) -> int:
    """Upserts every source in the YAML file into the DB (by name+url).
    Existing sources are updated in place; nothing is deleted, so sources
    added directly via the CLI/DB are left untouched."""
    sources_file = load_sources_file(path)
    count = 0
    for entry in sources_file.sources:
        upsert_source(
            session,
            name=entry.name,
            type_=entry.type,
            url=entry.url,
            enabled=entry.enabled,
            poll_interval_sec=entry.poll_interval_sec,
            respect_robots=entry.respect_robots,
            download_media=entry.download_media,
            config=entry.config.model_dump() if hasattr(entry.config, "model_dump") else entry.config,
        )
        count += 1
    logger.info("sources_seeded", count=count, path=str(path))
    return count
