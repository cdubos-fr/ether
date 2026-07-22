"""Tests for `ether.config.get_settings`'s project-root resolution and validation."""

from __future__ import annotations

from typing import TYPE_CHECKING

import pytest

from ether.config import ConfigError

if TYPE_CHECKING:  # pragma: no cover
    from pathlib import Path


class TestGetSettings:
    def test_valid_project_resolves(self, ether_env: None, project_root: Path) -> None:
        from ether.config import get_settings

        settings = get_settings()

        assert settings.project_root == project_root
        assert settings.univers_path == project_root / 'univers'
        assert settings.stories_path == project_root / 'stories'
        assert settings.config_path == project_root / 'config'

    def test_missing_env_var_raises(self, monkeypatch: pytest.MonkeyPatch) -> None:
        from ether import config

        monkeypatch.delenv('ETHER_PROJECT_ROOT', raising=False)
        config.get_settings.cache_clear()

        with pytest.raises(ConfigError, match='ETHER_PROJECT_ROOT is not set'):
            config.get_settings()
        config.get_settings.cache_clear()

    def test_invalid_project_raises_with_every_issue(
        self,
        project_root: Path,
        monkeypatch: pytest.MonkeyPatch,
    ) -> None:
        from ether import config

        (project_root / 'stories' / 'saga-test' / '_manifest.md').unlink()
        (project_root / 'univers' / 'lieux' / '_template.md').unlink()

        monkeypatch.setenv('ETHER_PROJECT_ROOT', str(project_root))
        config.get_settings.cache_clear()

        with pytest.raises(ConfigError) as exc_info:
            config.get_settings()
        config.get_settings.cache_clear()

        message = str(exc_info.value)
        assert 'saga-test' in message
        assert '_manifest.md' in message
        assert 'lieux' in message
        assert '_template.md' in message

    def test_default_saga_picks_first_alphabetically(self, ether_env: None) -> None:
        from ether.config import get_settings

        assert get_settings().default_saga == 'one-shot-test'
