"""Walk a project's `stories/` tree and yield the story nodes it contains.

Deliberately lenient: this only best-effort discovers whatever's there
(mirroring `ether.univers.scanner`'s malformed-file-becomes-an-issue
behavior). Whether the tree fully matches the required shape is
`ether.project.find_issues`'s job, not this one's.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import TYPE_CHECKING

from ether.markdown_io import FrontmatterError
from ether.project import CHAPTER_DIRNAME
from ether.project import INDEX_FILENAME
from ether.project import is_act_folder
from ether.stories import frontmatter

if TYPE_CHECKING:  # pragma: no cover
    from collections.abc import Iterable
    from pathlib import Path

    from ether.stories.schema import StoryFrontmatter


@dataclass
class RawStoryNode:
    """A single story node discovered on disk, with its parsed frontmatter."""

    meta: StoryFrontmatter
    body: str
    path: Path
    relative_path: Path
    saga: str
    tome: str = ''
    is_index: bool = False


@dataclass
class ScanIssue:
    """A markdown file that could not be parsed as a story node."""

    path: Path
    error: str


@dataclass
class ScanResult:
    """Outcome of walking a project's stories tree."""

    nodes: list[RawStoryNode]
    issues: list[ScanIssue]


def _subdirs(path: Path) -> list[Path]:
    return sorted(p for p in path.iterdir() if p.is_dir())


def _add_node(
    path: Path,
    root: Path,
    saga: str,
    tome: str,
    *,
    is_index: bool,
    nodes: list[RawStoryNode],
    issues: list[ScanIssue],
) -> None:
    try:
        meta, body = frontmatter.parse_file(path)
    except FrontmatterError as exc:
        issues.append(ScanIssue(path=path, error=str(exc)))
        return
    nodes.append(
        RawStoryNode(
            meta=meta,
            body=body,
            path=path,
            relative_path=path.relative_to(root),
            saga=saga,
            tome=tome,
            is_index=is_index,
        ),
    )


def _walk_act(
    act: Path,
    root: Path,
    saga: str,
    tome: str,
    nodes: list[RawStoryNode],
    issues: list[ScanIssue],
) -> None:
    index_path = act / INDEX_FILENAME
    if index_path.is_file():
        _add_node(index_path, root, saga, tome, is_index=True, nodes=nodes, issues=issues)
    chapter_dir = act / CHAPTER_DIRNAME
    if chapter_dir.is_dir():
        for chapter_path in sorted(chapter_dir.glob('*.md')):
            _add_node(chapter_path, root, saga, tome, is_index=False, nodes=nodes, issues=issues)


def _act_folders(path: Path) -> Iterable[Path]:
    return (d for d in _subdirs(path) if is_act_folder(d))


def walk_repo(root: Path) -> ScanResult:
    """Walk `root` (a project's `stories/` folder) for every story node."""
    nodes: list[RawStoryNode] = []
    issues: list[ScanIssue] = []
    if not root.is_dir():
        return ScanResult(nodes=nodes, issues=issues)

    stories_index = root / INDEX_FILENAME
    if stories_index.is_file():
        _add_node(stories_index, root, saga='', tome='', is_index=True, nodes=nodes, issues=issues)

    for story in _subdirs(root):
        saga = story.name
        direct_acts = list(_act_folders(story))
        if direct_acts:
            # One-shot shape: the story's own subfolders are acts.
            story_index = story / INDEX_FILENAME
            if story_index.is_file():
                _add_node(story_index, root, saga, '', is_index=True, nodes=nodes, issues=issues)
            for act in direct_acts:
                _walk_act(act, root, saga, '', nodes, issues)
            continue

        # Saga shape: the story's subfolders are tomes, each holding acts.
        for tome in _subdirs(story):
            tome_index = tome / INDEX_FILENAME
            if tome_index.is_file():
                _add_node(
                    tome_index,
                    root,
                    saga,
                    tome.name,
                    is_index=True,
                    nodes=nodes,
                    issues=issues,
                )
            for act in _act_folders(tome):
                _walk_act(act, root, saga, tome.name, nodes, issues)

    return ScanResult(nodes=nodes, issues=issues)
