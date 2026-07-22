"""Validate that a project root matches ether's fixed layout.

Unlike the free-text conventions inside `univers/` (category names, fiche
`type` values) and inside `stories/` (saga/tome/act/chapter names), the
top-level project shape itself is a contract ether enforces: `univers/`,
`stories/`, `config/`, and the required files at each level of `stories/`.

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
    if not (tome / INDEX_FILENAME).is_file():
        issues.append(f'{tome}/ is missing {INDEX_FILENAME}')
    acts = [d for d in _subdirs(tome) if is_act_folder(d)]
    if not acts:
        issues.append(f'{tome}/ has no act folders (a subfolder with a {CHAPTER_DIRNAME}/ inside)')
    for act in acts:
        _check_act(act, issues)


def _check_story(story: Path, issues: list[str]) -> None:
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

    # Saga shape: this story's subfolders are tomes, each holding acts.
    if not children:
        issues.append(f'{story}/ has no tome or act folders')
    for tome in children:
        _check_tome(tome, issues)


def _check_univers(univers: Path, issues: list[str]) -> None:
    if not univers.is_dir():
        issues.append(f'missing: {univers}/')
        return
    for category in _subdirs(univers):
        if not (category / INDEX_FILENAME).is_file():
            issues.append(f'{category}/ is missing {INDEX_FILENAME}')
        if not (category / TEMPLATE_FILENAME).is_file():
            issues.append(f'{category}/ is missing {TEMPLATE_FILENAME}')


def _check_stories(stories: Path, issues: list[str]) -> None:
    if not stories.is_dir():
        issues.append(f'missing: {stories}/')
        return
    if not (stories / INDEX_FILENAME).is_file():
        issues.append(f'{stories}/ is missing {INDEX_FILENAME}')
    for story in _subdirs(stories):
        _check_story(story, issues)


def find_issues(root: Path) -> list[str]:
    """Return every way `root` fails to match the required project layout.

    Empty list means the project is valid. Never raises on its own — see the
    module docstring for why (`ether.config.get_settings` turns a non-empty
    result into a single `ConfigError`).
    """
    issues: list[str] = []
    _check_univers(root / 'univers', issues)
    _check_stories(root / 'stories', issues)
    if not (root / 'config').is_dir():
        issues.append(f'missing: {root / "config"}/')
    return issues
