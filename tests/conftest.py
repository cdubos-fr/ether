"""Shared pytest fixtures: an isolated copy of the project fixture tree per test."""

from __future__ import annotations

import shutil
from pathlib import Path
from typing import TYPE_CHECKING

import pytest

if TYPE_CHECKING:  # pragma: no cover
    from collections.abc import Iterator

    from ether.stories.indexer import StoriesIndexStats
    from ether.univers.indexer import IndexStats

FIXTURE_SOURCE = Path(__file__).parent / 'fixtures' / 'project_min'


@pytest.fixture
def project_root(tmp_path: Path) -> Path:
    """A private, per-test copy of the synthetic ether project fixture."""
    dest = tmp_path / 'project'
    shutil.copytree(FIXTURE_SOURCE, dest)
    return dest


@pytest.fixture
def univers_root(project_root: Path) -> Path:
    """The fixture project's `univers/` subfolder."""
    return project_root / 'univers'


@pytest.fixture
def stories_root(project_root: Path) -> Path:
    """The fixture project's `stories/` subfolder."""
    return project_root / 'stories'


@pytest.fixture
def ether_env(
    project_root: Path,
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> Iterator[None]:
    """Point ether's config at the isolated fixture project and a scratch DB."""
    monkeypatch.setenv('ETHER_PROJECT_ROOT', str(project_root))
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
    """Fully index the fixture project's univers tree before a test runs."""
    from ether.db import get_session
    from ether.univers.indexer import reindex

    with get_session() as session:
        return reindex(univers_root, session)


@pytest.fixture
def stories_indexed(ether_env: None, stories_root: Path) -> StoriesIndexStats:
    """Fully index the fixture project's stories tree before a test runs."""
    from ether.db import get_session
    from ether.stories.indexer import reindex

    with get_session() as session:
        return reindex(stories_root, session)


@pytest.fixture
def client(indexed: IndexStats, stories_indexed: StoriesIndexStats):  # noqa: ANN201, ARG001
    """A `TestClient` against the app, with the fixture project already indexed."""
    from fastapi.testclient import TestClient

    from ether.main import app

    return TestClient(app)
