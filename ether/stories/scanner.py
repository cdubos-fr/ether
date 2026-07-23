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
from ether.project import ARCS_DIRNAME
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


def _walk_arcs(
    story: Path,
    root: Path,
    saga: str,
    nodes: list[RawStoryNode],
    issues: list[ScanIssue],
) -> None:
    arcs_dir = story / ARCS_DIRNAME
    if not arcs_dir.is_dir():
        return
    for arc_path in sorted(arcs_dir.glob('*.md')):
        _add_node(arc_path, root, saga, '', is_index=False, nodes=nodes, issues=issues)


def _walk_one_shot(
    story: Path,
    root: Path,
    saga: str,
    direct_acts: list[Path],
    nodes: list[RawStoryNode],
    issues: list[ScanIssue],
) -> None:
    story_index = story / INDEX_FILENAME
    if story_index.is_file():
        _add_node(story_index, root, saga, '', is_index=True, nodes=nodes, issues=issues)
    for act in direct_acts:
        _walk_act(act, root, saga, '', nodes, issues)


def _walk_saga_tomes(
    story: Path,
    root: Path,
    saga: str,
    nodes: list[RawStoryNode],
    issues: list[ScanIssue],
) -> None:
    # A saga's own `_index.md` is optional (unlike a one-shot's, which is
    # required) -- there's nothing structural riding on it, it's just an
    # optional place to give the saga itself a name/status/related distinct
    # from its folder slug.
    story_index = story / INDEX_FILENAME
    if story_index.is_file():
        _add_node(story_index, root, saga, '', is_index=True, nodes=nodes, issues=issues)
    for tome in _subdirs(story):
        if tome.name == ARCS_DIRNAME:
            continue
        tome_index = tome / INDEX_FILENAME
        if tome_index.is_file():
            _add_node(tome_index, root, saga, tome.name, is_index=True, nodes=nodes, issues=issues)
        for act in _act_folders(tome):
            _walk_act(act, root, saga, tome.name, nodes, issues)


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
        _walk_arcs(story, root, saga, nodes, issues)

        direct_acts = list(_act_folders(story))
        if direct_acts:
            _walk_one_shot(story, root, saga, direct_acts, nodes, issues)
        else:
            _walk_saga_tomes(story, root, saga, nodes, issues)

    return ScanResult(nodes=nodes, issues=issues)
