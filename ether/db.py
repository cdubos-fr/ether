"""Application database: the runtime index caches for univers and stories.

Both `ether.univers.index_models` and `ether.stories.index_models` are
disposable caches — see those modules' docstrings for the invariant.
Markdown is always the source of truth; nothing here is ever the sole copy
of a piece of content.
"""

from __future__ import annotations

from contextlib import contextmanager
from functools import lru_cache
from typing import TYPE_CHECKING

from sqlmodel import Session
from sqlmodel import SQLModel
from sqlmodel import create_engine

from ether.config import get_settings

if TYPE_CHECKING:  # pragma: no cover
    from collections.abc import Iterator

    from sqlalchemy.engine import Engine


@lru_cache(maxsize=1)
def get_engine() -> Engine:
    """Return the process-wide SQLModel engine.

    Memoized (same pattern as `ether.config.get_settings`) rather than a
    module-level `global`: the cache itself is the single source of truth
    for "has this been created yet", so there's no separate flag to keep in
    sync by hand.
    """
    return create_engine(get_settings().database_url, echo=False)


@lru_cache(maxsize=1)
def _ensure_initialized() -> bool:
    """Create all tables exactly once per process (memoized, see `get_engine`)."""
    from ether.stories import index_models as stories_index_models  # noqa: F401
    from ether.univers import index_models  # noqa: F401

    SQLModel.metadata.create_all(get_engine())
    return True


def init_db() -> None:
    """Create all tables (both indexes) — idempotent, safe to call repeatedly."""
    _ensure_initialized()


@contextmanager
def get_session() -> Iterator[Session]:
    """Yield a SQLModel session, lazily bootstrapping tables on first use."""
    _ensure_initialized()
    with Session(get_engine()) as session:
        yield session


def reset_engine_cache() -> None:
    """Dispose the cached engine and drop all memoized state (test helper for isolated DB paths)."""
    if get_engine.cache_info().currsize:
        get_engine().dispose()
    get_engine.cache_clear()
    _ensure_initialized.cache_clear()
