"""Application configuration, resolved once per process from environment variables.

Kept deliberately minimal ("easy to setup"): the only required setting is the
path to an ether project root — a folder with `univers/`, `stories/` and
`config/` subfolders matching the shape `ether.project.find_issues` checks.
"""

from __future__ import annotations

import os
from dataclasses import dataclass
from functools import lru_cache
from pathlib import Path

from dotenv import load_dotenv

from ether.project import find_issues

load_dotenv()


class ConfigError(RuntimeError):
    """Raised when required configuration is missing or invalid."""


@dataclass(frozen=True)
class EtherSettings:
    """Runtime configuration for a single ether project."""

    project_root: Path
    univers_path: Path
    stories_path: Path
    config_path: Path
    db_path: Path
    ai_backend: str
    gemini_api_key: str | None
    gemini_model: str
    anthropic_api_key: str | None
    claude_model: str
    host: str
    port: int

    @property
    def database_url(self) -> str:
        """SQLAlchemy connection URL for the runtime index database."""
        return f'sqlite:///{self.db_path}'

    def manifest_path_for(self, saga: str) -> Path:
        """Path to a given saga/one-shot's style manifest (scoped per-story, not global)."""
        return self.stories_path / saga / '_manifest.md'

    @property
    def default_saga(self) -> str:
        """First saga/one-shot folder under `stories/`, sorted by name.

        Interim stand-in for callers that predate manifests being per-saga
        (AI drafting for univers fiches, the sequencer's redaction context)
        until they're wired up to a real saga picker — see the "explicitly
        out of scope" section of the stories-layout plan.
        """
        if not self.stories_path.is_dir():
            return ''
        names = sorted(p.name for p in self.stories_path.iterdir() if p.is_dir())
        return names[0] if names else ''


def _repo_root() -> Path:
    return Path(__file__).resolve().parents[1]


def _resolve_project_root() -> Path:
    raw = os.getenv('ETHER_PROJECT_ROOT')
    if not raw:
        msg = (
            'ETHER_PROJECT_ROOT is not set: point it at an ether project '
            'root (univers/, stories/, config/).'
        )
        raise ConfigError(msg)
    path = Path(raw).expanduser().resolve()
    if not path.is_dir():
        msg = f'ETHER_PROJECT_ROOT does not exist or is not a directory: {path}'
        raise ConfigError(msg)
    return path


@lru_cache(maxsize=1)
def get_settings() -> EtherSettings:
    """Build (and cache) settings from the current environment."""
    project_root = _resolve_project_root()

    issues = find_issues(project_root)
    if issues:
        listing = '\n'.join(f'  - {issue}' for issue in issues)
        msg = f'invalid ether project at {project_root}:\n{listing}'
        raise ConfigError(msg)

    db_path = (
        Path(
            os.getenv('ETHER_DB_PATH', str(_repo_root() / 'data' / 'ether.db')),
        )
        .expanduser()
        .resolve()
    )
    db_path.parent.mkdir(parents=True, exist_ok=True)

    return EtherSettings(
        project_root=project_root,
        univers_path=project_root / 'univers',
        stories_path=project_root / 'stories',
        config_path=project_root / 'config',
        db_path=db_path,
        ai_backend=os.getenv('AI_BACKEND', 'stub').lower(),
        gemini_api_key=os.getenv('GEMINI_API_KEY') or None,
        gemini_model=os.getenv('GEMINI_MODEL', 'gemini-1.5-flash'),
        anthropic_api_key=os.getenv('ANTHROPIC_API_KEY') or None,
        claude_model=os.getenv('CLAUDE_MODEL', 'claude-sonnet-5'),
        host=os.getenv('ETHER_HOST', '127.0.0.1'),
        port=int(os.getenv('ETHER_PORT', '8000')),
    )
