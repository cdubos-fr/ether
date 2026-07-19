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
        help='Univers repo root to index.',
    ),
) -> None:
    """Reindex a univers repository into the runtime SQLite cache."""
    from ether.db import get_session
    from ether.db import init_db
    from ether.univers.indexer import reindex

    init_db()
    with get_session() as session:
        stats = reindex(path.resolve(), session)

    plural = '' if stats.items == 1 else 's'
    typer.echo(
        f'Indexed {stats.items} item{plural}, {stats.links} link(s) '
        f'({stats.dangling_links} dangling).',
    )
    for error in stats.parse_errors:
        typer.echo(f'  ! {error}', err=True)


if __name__ == '__main__':  # pragma: no cover
    app()
