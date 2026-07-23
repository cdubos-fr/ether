"""Cross-domain `related:` link graph, shared by `ether.univers` and `ether.stories`.

A `related:` id can point at a univers fiche *or* a story node (a character
referencing an arc-narratif, an arc referencing characters, a chapter
referencing an arc, ...), so the graph can't be scoped to either domain's own
tables. `EtherLink` lives here instead — no foreign keys, since a source or
target id can resolve against either `ether.univers.index_models.EtherItem`
or `ether.stories.index_models.EtherStoryItem`. Same disposable-cache
invariant as those two tables: rebuilt from scratch by `reindex()`/kept in
sync by `reindex_one()` in both domains, never the sole copy of anything.

`dangling` is never trusted mid-rebuild: `replace_source_links` only records
raw edges, and `recompute_dangling` (called once at the end of every
`reindex`/`reindex_one`, in both domains) is what actually marks a target as
known or not against the *current* state of both item tables. Doing it any
other way would make a link look dangling just because the other domain
hadn't reindexed yet in the same run (e.g. a character's arc reference,
checked while `ether.univers.indexer.reindex` runs before
`ether.stories.indexer.reindex` has had its turn).
"""

from __future__ import annotations

import posixpath
import re
from typing import TYPE_CHECKING
from typing import TypedDict

from sqlmodel import Field
from sqlmodel import SQLModel
from sqlmodel import delete
from sqlmodel import select

from ether.stories.index_models import EtherStoryItem
from ether.univers.index_models import EtherItem

if TYPE_CHECKING:  # pragma: no cover
    from collections.abc import Iterable
    from collections.abc import Mapping
    from pathlib import Path

    from sqlmodel import Session

ResolvedItem = EtherItem | EtherStoryItem

_MD_LINK_RE = re.compile(
    r'(?P<bang>!?)\[(?P<text>[^\[\]]*)\]\((?P<path>[^()\s]+\.md)(?P<fragment>#[^()\s]*)?\)',
)


class EtherLink(SQLModel, table=True):
    """A resolved `related:` reference from one item to another, either domain."""

    source_id: str = Field(primary_key=True)
    target_id: str = Field(primary_key=True)
    dangling: bool = Field(default=False)


class LinkView(TypedDict):
    """A related link, resolved and ready for template rendering."""

    id: str
    name: str | None
    url: str | None


def known_ids(session: Session) -> set[str]:
    """Every id currently indexed, across both univers fiches and story nodes."""
    ids = set(session.exec(select(EtherItem.id)).all())
    ids |= set(session.exec(select(EtherStoryItem.id)).all())
    return ids


def replace_source_links(session: Session, source_id: str, related: Iterable[str]) -> None:
    """Delete + reinsert `source_id`'s outgoing links.

    `dangling` is left `False` as a placeholder — always follow this with a
    `recompute_dangling()` call once every domain involved has finished
    indexing, or it may be wrong.
    """
    session.exec(delete(EtherLink).where(EtherLink.source_id == source_id))  # type: ignore[arg-type]  # ty:ignore[invalid-argument-type]
    for target in dict.fromkeys(related):
        session.add(EtherLink(source_id=source_id, target_id=target, dangling=False))


def recompute_dangling(session: Session) -> None:
    """Recheck every link's `target_id` against the current cross-domain known ids."""
    ids = known_ids(session)
    for link in session.exec(select(EtherLink)):
        link.dangling = link.target_id not in ids
        session.add(link)
    session.commit()


def delete_links_from(session: Session, source_ids: Iterable[str]) -> None:
    """Delete every outgoing link whose source is one of `source_ids`.

    Used by each domain's own `reindex()` to clear exactly its own
    previously-known sources before rebuilding — not the whole shared table,
    which would wipe the *other* domain's links too, and not a per-node
    `replace_source_links` loop alone, which never touches a node that was
    removed since the last reindex (its stale links would otherwise linger).
    """
    ids = list(source_ids)
    if not ids:
        return
    session.exec(delete(EtherLink).where(EtherLink.source_id.in_(ids)))  # type: ignore[attr-defined]  # ty:ignore[unresolved-attribute]


def resolve_item(session: Session, item_id: str) -> ResolvedItem | None:
    """Return the `EtherItem` or `EtherStoryItem` for `item_id`, whichever domain it's in."""
    found = session.get(EtherItem, item_id)
    if found is not None:
        return found
    return session.get(EtherStoryItem, item_id)


def item_url(item: ResolvedItem) -> str:
    """Return the app route for a resolved item, whichever domain it came from."""
    if isinstance(item, EtherItem):
        return f'/item/{item.id}'
    if item.type.startswith('arc-'):
        return f'/stories/arcs/{item.id}'
    if item.type == 'chapitre':
        return f'/stories/chapters/{item.id}'
    if item.type == 'acte':
        return f'/stories/actes/{item.id}'
    if item.type == 'tome':
        return f'/stories/tomes/{item.id}'
    return f'/stories/{item.saga}' if item.saga else '/stories'


def _view_for(session: Session, item_id: str, *, dangling: bool) -> LinkView:
    if dangling:
        return LinkView(id=item_id, name=None, url=None)
    resolved = resolve_item(session, item_id)
    if resolved is None:
        return LinkView(id=item_id, name=None, url=None)
    return LinkView(id=item_id, name=resolved.name, url=item_url(resolved))


def outgoing_views(session: Session, item_id: str) -> list[LinkView]:
    """`related` references from `item_id`, resolved across both domains."""
    rows = session.exec(select(EtherLink).where(EtherLink.source_id == item_id))
    return [_view_for(session, row.target_id, dangling=row.dangling) for row in rows]


def backlink_views(session: Session, item_id: str) -> list[LinkView]:
    """Every item (either domain) whose `related` list references `item_id`."""
    rows = session.exec(
        select(EtherLink.source_id).where(
            EtherLink.target_id == item_id,
            EtherLink.dangling == False,  # noqa: E712 - SQLAlchemy expression, not a Python bool
        ),
    ).all()
    return [_view_for(session, source_id, dangling=False) for source_id in sorted(set(rows))]


def url_index(session: Session) -> dict[str, str]:
    """Every indexed item's project-root-relative path -> its resolved app URL.

    Feeds `rewrite_relative_links` so prose links resolve regardless of
    which domain (or which folder within it) the target actually lives in.
    """
    index: dict[str, str] = {}
    for item in session.exec(select(EtherItem)):
        index[f'univers/{item.relative_path}'] = item_url(item)
    for story_item in session.exec(select(EtherStoryItem)):
        index[f'stories/{story_item.relative_path}'] = item_url(story_item)
    return index


def rewrite_relative_links(
    body: str,
    current_relative_path: Path,
    path_to_url: Mapping[str, str],
) -> str:
    """Rewrite `[text](relative/path.md)` links to their resolved app route.

    `current_relative_path` is the item's own project-root-relative path
    (e.g. `univers/personnages/hero.md` or `stories/saga/arcs/arc-x.md`),
    used as the base for resolving `../`-relative targets; `path_to_url` maps
    every indexed item's project-root-relative path to its app URL (see
    `url_index`). Images (`![...](...)`) are left alone. Links that don't
    resolve to a currently-indexed item are left exactly as written.
    """
    base = current_relative_path.parent

    def _replace(match: re.Match[str]) -> str:
        if match.group('bang'):
            return match.group(0)
        target = posixpath.normpath(posixpath.join(str(base), match.group('path')))
        url = path_to_url.get(target)
        if url is None:
            return match.group(0)
        fragment = match.group('fragment') or ''
        return f'[{match.group("text")}]({url}{fragment})'

    return _MD_LINK_RE.sub(_replace, body)
