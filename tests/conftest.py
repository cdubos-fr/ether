"""Shared pytest fixtures: an isolated copy of the univers fixture repo per test."""

from __future__ import annotations

import shutil
from pathlib import Path
from typing import TYPE_CHECKING

import pytest

if TYPE_CHECKING:  # pragma: no cover
    from collections.abc import Iterator

    from ether.univers.indexer import IndexStats

FIXTURE_SOURCE = Path(__file__).parent / 'fixtures' / 'univers_min'


@pytest.fixture
def univers_root(tmp_path: Path) -> Path:
    """A private, per-test copy of the synthetic univers fixture repo."""
    dest = tmp_path / 'univers'
    shutil.copytree(FIXTURE_SOURCE, dest)
    return dest


@pytest.fixture
def ether_env(
    univers_root: Path,
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> Iterator[None]:
    """Point ether's config at the isolated fixture repo and a scratch DB."""
    monkeypatch.setenv('ETHER_UNIVERS_PATH', str(univers_root))
    monkeypatch.setenv('ETHER_DB_PATH', str(tmp_path / 'ether.db'))
    monkeypatch.setenv('AI_BACKEND', 'stub')
    monkeypatch.delenv('GEMINI_API_KEY', raising=False)
    monkeypatch.delenv('ANTHROPIC_API_KEY', raising=False)

    from ether import config
    from ether import db

    config.get_settings.cache_clear()
    db.reset_engine_cache()
    db.init_db()
    yield
    config.get_settings.cache_clear()
    db.reset_engine_cache()


@pytest.fixture
def indexed(ether_env: None, univers_root: Path) -> IndexStats:
    """Fully index the fixture repo before a test runs."""
    from ether.db import get_session
    from ether.univers.indexer import reindex

    with get_session() as session:
        return reindex(univers_root, session)


@pytest.fixture
def client(indexed: IndexStats):  # noqa: ANN201, ARG001
    """A `TestClient` against the app, with the fixture repo already indexed."""
    from fastapi.testclient import TestClient

    from ether.main import app

    return TestClient(app)
