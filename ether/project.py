"""Validate that a project root matches ether's fixed layout.

Unlike the free-text conventions inside `univers/` (category names, fiche
`type` values) and inside `stories/` (saga/tome/act/chapter names), the shape
of each level itself is a contract ether enforces — but only for what's
actually there: nothing is required to exist upfront. `univers/`, `stories/`
and `config/` may all be absent or empty; a saga may have zero tomes, a tome
may have zero acts, an act may have zero chapters. The UI is expected to
scaffold a level's required files atomically at the moment something is
created under it (the same way `ether.ai.style_manifest.ensure_manifest`
already scaffolds a manifest lazily) — `find_issues` only catches a level
that exists but is missing its *own* required files, not a level that simply
hasn't been created yet.

`find_issues` never raises — it collects every problem it finds so
`ether.config.get_settings` can report them all at once instead of
fail-fast-on-the-first. See that module for how issues become a `ConfigError`.
"""

from __future__ import annotations

from typing import TYPE_CHECKING

if TYPE_CHECKING:  # pragma: no cover
    from pathlib import Path

CHAPTER_DIRNAME = '_chapter'
INDEX_FILENAME = '_index.md'
TEMPLATE_FILENAME = '_template.md'
MANIFEST_FILENAME = '_manifest.md'


def is_act_folder(path: Path) -> bool:
    """Return whether `path` is an act folder (has a `_chapter/` subfolder directly inside it)."""
    return (path / CHAPTER_DIRNAME).is_dir()


def _subdirs(path: Path) -> list[Path]:
    return sorted(p for p in path.iterdir() if p.is_dir())


def _check_act(act: Path, issues: list[str]) -> None:
    if not (act / INDEX_FILENAME).is_file():
        issues.append(f'{act}/ is missing {INDEX_FILENAME}')


def _check_tome(tome: Path, issues: list[str]) -> None:
    """Require the tome's own `_index.md`; it may have zero act folders so far."""
    if not (tome / INDEX_FILENAME).is_file():
        issues.append(f'{tome}/ is missing {INDEX_FILENAME}')
    for act in (d for d in _subdirs(tome) if is_act_folder(d)):
        _check_act(act, issues)


def _check_story(story: Path, issues: list[str]) -> None:
    """Require the saga/one-shot's own `_manifest.md`; it may have zero tomes/acts so far."""
    if not (story / MANIFEST_FILENAME).is_file():
        issues.append(f'{story}/ is missing {MANIFEST_FILENAME}')

    children = _subdirs(story)
    direct_acts = [d for d in children if is_act_folder(d)]
    if direct_acts:
        # One-shot shape: this story's own subfolders are acts.
        if not (story / INDEX_FILENAME).is_file():
            issues.append(f'{story}/ is missing {INDEX_FILENAME}')
        for act in direct_acts:
            _check_act(act, issues)
        return

    # Saga shape: this story's subfolders (if any) are tomes, each holding acts.
    for tome in children:
        _check_tome(tome, issues)


def _check_univers(univers: Path, issues: list[str]) -> None:
    """`univers/` may be absent or empty; a category that exists needs its own two files."""
    if not univers.is_dir():
        return
    for category in _subdirs(univers):
        if not (category / INDEX_FILENAME).is_file():
            issues.append(f'{category}/ is missing {INDEX_FILENAME}')
        if not (category / TEMPLATE_FILENAME).is_file():
            issues.append(f'{category}/ is missing {TEMPLATE_FILENAME}')


def _check_stories(stories: Path, issues: list[str]) -> None:
    """`stories/` may be absent or empty (zero sagas/one-shots so far)."""
    if not stories.is_dir():
        return
    if not (stories / INDEX_FILENAME).is_file():
        issues.append(f'{stories}/ is missing {INDEX_FILENAME}')
    for story in _subdirs(stories):
        _check_story(story, issues)


def find_issues(root: Path) -> list[str]:
    """Return every way something under `root` is malformed, given what's actually there.

    Empty list means the project is valid — including a brand-new, entirely
    empty project. Never raises on its own — see the module docstring for why
    (`ether.config.get_settings` turns a non-empty result into a single
    `ConfigError`).
    """
    issues: list[str] = []
    _check_univers(root / 'univers', issues)
    _check_stories(root / 'stories', issues)
    return issues
