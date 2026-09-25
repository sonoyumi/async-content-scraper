from __future__ import annotations

import asyncio
import json

import typer
from pydantic import BaseModel
from rich.console import Console
from rich.table import Table

from scraper.logging_config import configure_logging, get_logger
from scraper.poller import poll_source
from scraper.settings import settings
from scraper.sources.loader import load_sources_file, seed_sources_from_file
from scraper.sources.service import build_extractor, build_fetcher, fetch_kwargs
from scraper.storage.database import init_db, session_scope
from scraper.storage.models import Source
from scraper.storage.repository import list_enabled_sources, upsert_source

app = typer.Typer(add_completion=False)
console = Console()
logger = get_logger(component="cli")


@app.callback()
def main() -> None:
    configure_logging()


@app.command("init-db")
def init_db_command() -> None:
    """Create all tables (idempotent)."""
    init_db()
    console.print("[green]Database schema is up to date.[/green]")


@app.command("seed")
def seed_command(
    config_file: str = typer.Option(settings.sources_config_path, "--config-file"),
) -> None:
    """Upsert every source defined in a YAML file into the DB."""
    init_db()
    with session_scope() as session:
        count = seed_sources_from_file(session, config_file)
    console.print(f"[green]Seeded/updated {count} source(s) from {config_file}.[/green]")


@app.command("add-source")
def add_source_command(
    name: str = typer.Option(...),
    type_: str = typer.Option(..., "--type", help="html | playwright | telegram"),
    url: str = typer.Option(...),
    config_json: str = typer.Option(..., "--config-json", help="JSON string with the type-specific config"),
    poll_interval_sec: int = typer.Option(settings.default_poll_interval_sec),
    enabled: bool = typer.Option(True),
    respect_robots: bool = typer.Option(True),
) -> None:
    """Add or update a single source directly from the command line."""
    init_db()
    with session_scope() as session:
        upsert_source(
            session,
            name=name,
            type_=type_,
            url=url,
            enabled=enabled,
            poll_interval_sec=poll_interval_sec,
            respect_robots=respect_robots,
            config=json.loads(config_json),
        )
    console.print(f"[green]Source '{name}' saved.[/green]")


@app.command("list-sources")
def list_sources_command() -> None:
    with session_scope() as session:
        sources = list_enabled_sources(session)

    table = Table(title="Enabled sources")
    for column in ("id", "name", "type", "poll_interval_sec", "last_success_at", "consecutive_errors"):
        table.add_column(column)
    for source in sources:
        table.add_row(
            str(source.id),
            source.name,
            source.type,
            str(source.poll_interval_sec),
            str(source.last_success_at or "-"),
            str(source.consecutive_errors),
        )
    console.print(table)


@app.command("status")
def status_command() -> None:
    with session_scope() as session:
        sources = list_enabled_sources(session)

    table = Table(title="Source status")
    for column in ("id", "name", "last_polled_at", "last_success_at", "consecutive_errors", "last_error"):
        table.add_column(column)
    for source in sources:
        table.add_row(
            str(source.id),
            source.name,
            str(source.last_polled_at or "-"),
            str(source.last_success_at or "-"),
            str(source.consecutive_errors),
            (source.last_error or "-")[:80],
        )
    console.print(table)


@app.command("test-source")
def test_source_command(
    config_file: str = typer.Option(settings.sources_config_path, "--config-file"),
    name: str = typer.Option(..., help="Name of the source entry in the YAML file"),
) -> None:
    """Fetch + extract a single source WITHOUT touching the database. Use this
    to quickly validate selectors/config on 1-2 sources before scheduling them."""
    sources_file = load_sources_file(config_file)
    entry = next((s for s in sources_file.sources if s.name == name), None)
    if entry is None:
        console.print(f"[red]No source named '{name}' found in {config_file}[/red]")
        raise typer.Exit(1)

    # Transient ORM object: never added to a session, so nothing is written to the DB.
    source = Source(
        name=entry.name,
        type=entry.type,
        url=entry.url,
        config=entry.config.model_dump() if isinstance(entry.config, BaseModel) else entry.config,
        respect_robots=entry.respect_robots,
    )
    fetcher = build_fetcher(source)
    extractor = build_extractor(source)
    kwargs = fetch_kwargs(source)

    async def _run():
        raw_html = await fetcher.fetch(entry.url, **kwargs)
        return extractor.extract(raw_html, base_url=entry.url)

    items = asyncio.run(_run())
    console.print(f"[bold]Extracted {len(items)} item(s) from '{name}'[/bold]")
    for item in items[:20]:
        console.print(
            {
                "external_id": item.external_id,
                "published_at": str(item.published_at),
                "url": item.url,
                "text_preview": (item.text or "")[:200],
                "media": item.media,
            }
        )


@app.command("poll-once")
def poll_once_command(source_id: int = typer.Option(...), notify: bool = typer.Option(True)) -> None:
    """Run one full poll cycle (fetch -> extract -> dedup -> store -> notify) for a source that already exists in the DB."""
    new_count = asyncio.run(poll_source(source_id, notify=notify))
    console.print(f"[green]{new_count} new post(s) stored for source {source_id}.[/green]")


@app.command("run")
def run_command() -> None:
    """Long-running entrypoint: seeds sources, then polls every enabled source on its own schedule."""
    from scraper.scheduler.runner import run_forever

    asyncio.run(run_forever())


if __name__ == "__main__":
    app()
