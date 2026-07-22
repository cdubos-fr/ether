"""Read/write access to individual story nodes on disk.

Mirrors `ether.univers.repository`: every edit lands on the markdown itself,
the DB is refreshed afterwards via a cheap single-file reindex (see
`ether.stories.indexer.reindex_one`). Covers every node shape (saga/one-shot,
tome, act, chapter) since they all share the same `StoryFrontmatter` contract.
"""

from __future__ import annotations

from typing import TYPE_CHECKING
from typing import Any

from filelock import FileLock

from ether.stories import frontmatter

if TYPE_CHECKING:  # pragma: no cover
    from pathlib import Path

    from ether.stories.schema import StoryFrontmatter


def _lock_path(root: Path) -> Path:
    lock_dir = root / '.ether'
    lock_dir.mkdir(exist_ok=True)
    return lock_dir / 'stories.lock'


def repo_lock(root: Path) -> FileLock:
    """File lock guarding a full reindex against concurrent single-file writes."""
    return FileLock(str(_lock_path(root)))


def _apply_meta(raw: dict[str, Any], meta: StoryFrontmatter) -> None:
    # `raw` is an existing file's loaded YAML mapping: it may carry extra,
    # author-defined keys beyond our fixed schema (see
    # `ether.univers.repository._apply_meta`'s identical rationale).
    raw['id'] = meta.id
    raw['type'] = meta.type
    raw['name'] = meta.name
    raw['aliases'] = frontmatter.flow_seq(raw.get('aliases'), list(meta.aliases))
    raw['status'] = meta.status
    raw['tags'] = frontmatter.flow_seq(raw.get('tags'), list(meta.tags))
    raw['related'] = frontmatter.flow_seq(raw.get('related'), list(meta.related))
    raw['updated'] = frontmatter.coerce_date(meta.updated)
    raw['numero'] = meta.numero
    raw['theme_specifique'] = meta.theme_specifique
    raw['question_centrale'] = meta.question_centrale
    raw['fonction_narrative'] = meta.fonction_narrative
    raw['etat_initial_protagoniste'] = meta.etat_initial_protagoniste
    raw['etat_final_protagoniste'] = meta.etat_final_protagoniste
    raw['scope'] = meta.scope


def write_node(root: Path, relative_path: str, meta: StoryFrontmatter, body: str) -> None:
    """Overwrite a story node's frontmatter + body.

    If the file already exists, its YAML mapping is loaded and mutated in
    place so key order/quoting of untouched fields survives; a brand-new file
    gets a fresh mapping in the repo's conventional field order.
    """
    path = root / relative_path
    with repo_lock(root):
        if path.is_file():
            raw, _old_body = frontmatter.load_raw(path)
            _apply_meta(raw, meta)
            frontmatter.write_file(path, raw, body)
        else:
            frontmatter.write_file(path, frontmatter.new_story_frontmatter_mapping(meta), body)
