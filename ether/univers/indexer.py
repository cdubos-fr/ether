"""Build/refresh the runtime index from a univers repository."""

from __future__ import annotations

import json
from dataclasses import dataclass
from typing import TYPE_CHECKING

from sqlmodel import delete
from sqlmodel import select

from ether.univers import frontmatter
from ether.univers.index_models import EtherItem
from ether.univers.index_models import EtherLink
from ether.univers.index_models import EtherTag
from ether.univers.scanner import INDEX_STEM
from ether.univers.scanner import RawFiche
from ether.univers.scanner import walk_repo

if TYPE_CHECKING:  # pragma: no cover
    from pathlib import Path

    from sqlmodel import Session


@dataclass
class IndexStats:
    """Outcome of a reindex pass."""

    items: int
    links: int
    dangling_links: int
    parse_errors: list[str]


def _excerpt(body: str, length: int = 240) -> str:
    text = ' '.join(body.split())
    return text[:length]


def _category_of(relative_path: Path) -> str:
    return relative_path.parts[0] if len(relative_path.parts) > 1 else ''


def _item_from_fiche(fiche: RawFiche) -> EtherItem:
    return EtherItem(
        id=fiche.meta.id,
        type=fiche.meta.type,
        name=fiche.meta.name,
        category=_category_of(fiche.relative_path),
        status=fiche.meta.status,
        aliases_json=json.dumps(fiche.meta.aliases, ensure_ascii=False),
        tags_json=json.dumps(fiche.meta.tags, ensure_ascii=False),
        updated=fiche.meta.updated,
        relative_path=str(fiche.relative_path),
        body_excerpt=_excerpt(fiche.body),
        is_index=fiche.is_index,
    )


def reindex(root: Path, session: Session) -> IndexStats:
    """Fully rebuild the index tables from the markdown tree rooted at `root`."""
    scan = walk_repo(root)

    session.exec(delete(EtherLink))
    session.exec(delete(EtherTag))
    session.exec(delete(EtherItem))

    known_ids: set[str] = set()
    for fiche in scan.fiches:
        item = _item_from_fiche(fiche)
        session.add(item)
        known_ids.add(item.id)
    session.commit()

    link_count = 0
    dangling_count = 0
    for fiche in scan.fiches:
        for target in dict.fromkeys(fiche.meta.related):
            dangling = target not in known_ids
            session.add(EtherLink(source_id=fiche.meta.id, target_id=target, dangling=dangling))
            link_count += 1
            dangling_count += int(dangling)
        for tag in dict.fromkeys(fiche.meta.tags):
            session.add(EtherTag(item_id=fiche.meta.id, tag=tag))
    session.commit()

    return IndexStats(
        items=len(scan.fiches),
        links=link_count,
        dangling_links=dangling_count,
        parse_errors=[f'{issue.path}: {issue.error}' for issue in scan.issues],
    )


def backlinks(session: Session, item_id: str) -> list[str]:
    """IDs of items whose `related` list references `item_id`."""
    rows = session.exec(
        select(EtherLink.source_id).where(
            EtherLink.target_id == item_id,
            EtherLink.dangling == False,  # noqa: E712 - SQLAlchemy expression, not a Python bool
        ),
    ).all()
    return sorted(set(rows))


def outgoing_links(session: Session, item_id: str) -> list[EtherLink]:
    """`related` references from `item_id`, including dangling ones."""
    return list(session.exec(select(EtherLink).where(EtherLink.source_id == item_id)).all())


def list_tags(session: Session) -> list[tuple[str, int]]:
    """Every tag in use, with how many fiches carry it, sorted alphabetically."""
    rows = session.exec(select(EtherTag.tag)).all()
    counts: dict[str, int] = {}
    for tag in rows:
        counts[tag] = counts.get(tag, 0) + 1
    return sorted(counts.items())


def items_with_tag(session: Session, tag: str) -> list[EtherItem]:
    """Every fiche carrying `tag`, across all categories — the point of tags."""
    item_ids = session.exec(select(EtherTag.item_id).where(EtherTag.tag == tag)).all()
    if not item_ids:
        return []
    query = select(EtherItem).where(EtherItem.id.in_(item_ids))  # type: ignore[attr-defined]  # ty:ignore[unresolved-attribute]
    query = query.order_by(EtherItem.name)
    return list(session.exec(query))


def path_index(session: Session) -> dict[str, str]:
    """Map every indexed fiche's repo-relative path to its id.

    Used to rewrite the plain relative markdown-file links fiches use in
    prose (`[Alice](../../personnages/.../alice.md)`, per the univers repo's
    own convention) into `/item/{id}` routes at render time — see
    `ether.univers.linkrewrite`.
    """
    rows = session.exec(select(EtherItem.relative_path, EtherItem.id)).all()
    return dict(rows)


def reindex_one(root: Path, relative_path: str, session: Session) -> EtherItem:
    """Refresh a single fiche's index rows after an in-app edit or creation.

    Cheaper than a full `reindex()` for the common case of one file changing;
    does not revisit other fiches' dangling status (an edit never removes an
    id another fiche already resolved against, only creation/deletion could,
    which go through `reindex()`).
    """
    path = root / relative_path
    meta, body = frontmatter.parse_file(path)
    relative = path.relative_to(root)
    fiche = RawFiche(
        meta=meta,
        body=body,
        path=path,
        relative_path=relative,
        is_index=relative.stem == INDEX_STEM,
    )
    item = _item_from_fiche(fiche)

    existing = session.get(EtherItem, item.id)
    if existing is not None:
        session.delete(existing)
    session.add(item)

    session.exec(delete(EtherLink).where(EtherLink.source_id == item.id))  # type: ignore[arg-type]  # ty:ignore[invalid-argument-type]
    for target in dict.fromkeys(meta.related):
        known = session.get(EtherItem, target) is not None
        session.add(EtherLink(source_id=item.id, target_id=target, dangling=not known))

    session.exec(delete(EtherTag).where(EtherTag.item_id == item.id))  # type: ignore[arg-type]  # ty:ignore[invalid-argument-type]
    for tag in dict.fromkeys(meta.tags):
        session.add(EtherTag(item_id=item.id, tag=tag))

    session.commit()
    return item
