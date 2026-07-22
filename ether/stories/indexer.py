"""Build/refresh the runtime stories index from a project's `stories/` tree."""

from __future__ import annotations

import json
from dataclasses import dataclass
from typing import TYPE_CHECKING

from sqlmodel import delete

from ether.project import INDEX_FILENAME
from ether.stories import frontmatter
from ether.stories.index_models import EtherStoryItem
from ether.stories.scanner import RawStoryNode
from ether.stories.scanner import walk_repo

if TYPE_CHECKING:  # pragma: no cover
    from pathlib import Path

    from sqlmodel import Session


@dataclass
class StoriesIndexStats:
    """Outcome of a stories reindex pass."""

    items: int
    parse_errors: list[str]


def _excerpt(body: str, length: int = 240) -> str:
    text = ' '.join(body.split())
    return text[:length]


def _item_from_node(node: RawStoryNode) -> EtherStoryItem:
    return EtherStoryItem(
        id=node.meta.id,
        type=node.meta.type,
        name=node.meta.name,
        saga=node.saga,
        tome=node.tome,
        status=node.meta.status,
        aliases_json=json.dumps(node.meta.aliases, ensure_ascii=False),
        tags_json=json.dumps(node.meta.tags, ensure_ascii=False),
        related_json=json.dumps(node.meta.related, ensure_ascii=False),
        updated=node.meta.updated,
        relative_path=str(node.relative_path),
        body_excerpt=_excerpt(node.body),
        is_index=node.is_index,
        numero=node.meta.numero,
        theme_specifique=node.meta.theme_specifique,
        question_centrale=node.meta.question_centrale,
        fonction_narrative=node.meta.fonction_narrative,
        etat_initial_protagoniste=node.meta.etat_initial_protagoniste,
        etat_final_protagoniste=node.meta.etat_final_protagoniste,
        scope=node.meta.scope,
    )


def reindex(root: Path, session: Session) -> StoriesIndexStats:
    """Fully rebuild the stories index tables from the markdown tree rooted at `root`."""
    scan = walk_repo(root)

    session.exec(delete(EtherStoryItem))

    for node in scan.nodes:
        session.add(_item_from_node(node))
    session.commit()

    return StoriesIndexStats(
        items=len(scan.nodes),
        parse_errors=[f'{issue.path}: {issue.error}' for issue in scan.issues],
    )


def reindex_one(
    root: Path,
    relative_path: str,
    saga: str,
    tome: str,
    session: Session,
) -> EtherStoryItem:
    """Refresh a single story node's index row after an in-app edit or creation.

    Cheaper than a full `reindex()` for the common case of one file changing.
    `saga`/`tome` must be supplied by the caller (unlike univers's
    `reindex_one`, position in the tree isn't derivable from `relative_path`
    alone once one-shots and sagas share the same node shapes).
    """
    path = root / relative_path
    meta, body = frontmatter.parse_file(path)
    relative = path.relative_to(root)
    node = RawStoryNode(
        meta=meta,
        body=body,
        path=path,
        relative_path=relative,
        saga=saga,
        tome=tome,
        is_index=path.name == INDEX_FILENAME,
    )
    item = _item_from_node(node)

    existing = session.get(EtherStoryItem, item.id)
    if existing is not None:
        session.delete(existing)
    session.add(item)
    session.commit()
    return item
