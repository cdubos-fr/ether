"""FastAPI application: mounts every feature router and static assets."""

from __future__ import annotations

from typing import TypedDict

from fastapi import FastAPI
from fastapi.staticfiles import StaticFiles

from ether.db import get_session
from ether.paths import STATIC_DIR
from ether.web.routers import browse
from ether.web.routers import create
from ether.web.routers import fiche_edit
from ether.web.routers import stories
from ether.web.routers import style
from ether.web.routers import tags

app = FastAPI(title='ether')
app.mount('/static', StaticFiles(directory=str(STATIC_DIR)), name='static')

app.include_router(browse.router)
app.include_router(fiche_edit.router)
app.include_router(create.router)
app.include_router(style.router)
app.include_router(stories.router)
app.include_router(tags.router)


class HealthStatus(TypedDict):
    """Response shape for `/healthz`."""

    status: str


@app.get('/healthz')
def healthz() -> HealthStatus:
    """Check basic liveness and DB connectivity."""
    with get_session() as _session:
        pass
    return HealthStatus(status='ok')
