"""Application configuration, resolved once per process from environment variables.

Kept deliberately minimal ("easy to setup"): the only required setting is the
path to a univers markdown repository.
"""

from __future__ import annotations

import os
from dataclasses import dataclass
from functools import lru_cache
from pathlib import Path

from dotenv import load_dotenv

load_dotenv()


class ConfigError(RuntimeError):
    """Raised when required configuration is missing or invalid."""


@dataclass(frozen=True)
class EtherSettings:
    """Runtime configuration for a single ether project."""

    univers_path: Path
    db_path: Path
    style_manifest_path: Path
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


def _repo_root() -> Path:
    return Path(__file__).resolve().parents[1]


def _resolve_univers_path() -> Path:
    raw = os.getenv('ETHER_UNIVERS_PATH')
    if not raw:
        msg = 'ETHER_UNIVERS_PATH is not set: point it at a markdown univers repository.'
        raise ConfigError(msg)
    path = Path(raw).expanduser().resolve()
    if not path.is_dir():
        msg = f'ETHER_UNIVERS_PATH does not exist or is not a directory: {path}'
        raise ConfigError(msg)
    return path


@lru_cache(maxsize=1)
def get_settings() -> EtherSettings:
    """Build (and cache) settings from the current environment."""
    univers_path = _resolve_univers_path()

    db_path = (
        Path(
            os.getenv('ETHER_DB_PATH', str(_repo_root() / 'data' / 'ether.db')),
        )
        .expanduser()
        .resolve()
    )
    db_path.parent.mkdir(parents=True, exist_ok=True)

    style_manifest_path = (
        Path(
            os.getenv('ETHER_STYLE_MANIFEST_PATH', str(univers_path / '_manifest.md')),
        )
        .expanduser()
        .resolve()
    )

    return EtherSettings(
        univers_path=univers_path,
        db_path=db_path,
        style_manifest_path=style_manifest_path,
        ai_backend=os.getenv('AI_BACKEND', 'stub').lower(),
        gemini_api_key=os.getenv('GEMINI_API_KEY') or None,
        gemini_model=os.getenv('GEMINI_MODEL', 'gemini-1.5-flash'),
        anthropic_api_key=os.getenv('ANTHROPIC_API_KEY') or None,
        claude_model=os.getenv('CLAUDE_MODEL', 'claude-sonnet-5'),
        host=os.getenv('ETHER_HOST', '127.0.0.1'),
        port=int(os.getenv('ETHER_PORT', '8000')),
    )
