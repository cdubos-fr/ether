"""Typer CLI for ether: `ether serve`, `ether index <path>`."""

from __future__ import annotations

from pathlib import Path  # noqa: TC003 - Typer needs this at runtime to resolve the annotation

import typer

app = typer.Typer(add_completion=False, help='World-building & redaction assistant.')


@app.command()
def serve(
    host: str | None = typer.Option(None, help='Listen address (default: $ETHER_HOST).'),
    port: int | None = typer.Option(None, help='Listen port (default: $ETHER_PORT).'),
    reload: bool = typer.Option(False, '--reload/--no-reload', help='Enable autoreload.'),  # noqa: FBT001
    log_level: str = typer.Option('info', help='Uvicorn log level.'),
) -> None:
    """Start the ether web application with Uvicorn."""
    import uvicorn

    from ether.config import get_settings

    settings = get_settings()
    uvicorn.run(
        'ether.main:app',
        host=host or settings.host,
        port=port or settings.port,
        reload=reload,
        log_level=log_level,
    )


@app.command(name='index')
def index_command(
    path: Path = typer.Argument(  # noqa: B008 - idiomatic Typer parameter-default pattern
        ...,
        exists=True,
        file_okay=False,
        help='Project root to index (must contain univers/, stories/, config/).',
    ),
) -> None:
    """Reindex a project's univers + stories markdown trees into the runtime SQLite cache."""
    from ether.db import get_session
    from ether.db import init_db
    from ether.project import find_issues
    from ether.stories.indexer import reindex as reindex_stories
    from ether.univers.indexer import reindex as reindex_univers

    root = path.resolve()
    issues = find_issues(root)
    if issues:
        typer.echo(f'invalid ether project at {root}:', err=True)
        for issue in issues:
            typer.echo(f'  - {issue}', err=True)
        raise typer.Exit(code=1)

    init_db()
    with get_session() as session:
        univers_stats = reindex_univers(root / 'univers', session)
        stories_stats = reindex_stories(root / 'stories', session)

    item_plural = '' if univers_stats.items == 1 else 's'
    typer.echo(
        f'univers: indexed {univers_stats.items} item{item_plural}, '
        f'{univers_stats.links} link(s) ({univers_stats.dangling_links} dangling).',
    )
    story_plural = '' if stories_stats.items == 1 else 's'
    typer.echo(f'stories: indexed {stories_stats.items} node{story_plural}.')

    for error in [*univers_stats.parse_errors, *stories_stats.parse_errors]:
        typer.echo(f'  ! {error}', err=True)


if __name__ == '__main__':  # pragma: no cover
    app()
