"""SQLModel tables for the runtime index — a disposable, rebuildable cache.

Invariant: deleting `ether.db` and re-running `ether index <path>` must
reproduce every row here from the markdown tree with zero data loss. Nothing
in this module is ever the sole copy of a piece of content — the markdown
files are always the source of truth (see `ether/univers/frontmatter.py`).

The `related:` link graph lives in `ether.link_graph` instead of here — a
link's source or target can be a univers fiche *or* a story node, so it isn't
scoped to this domain.
"""

from __future__ import annotations

from sqlmodel import Field
from sqlmodel import SQLModel


class EtherItem(SQLModel, table=True):
    """One indexed fiche, mirroring the fields of its markdown frontmatter."""

    id: str = Field(primary_key=True)
    type: str = Field(index=True)
    name: str = Field(index=True)
    category: str = Field(index=True)
    status: str = Field(default='brouillon', index=True)
    aliases_json: str = Field(default='[]')
    tags_json: str = Field(default='[]')
    updated: str = Field(default='')
    relative_path: str
    body_excerpt: str = Field(default='')
    is_index: bool = Field(default=False, index=True)


class EtherTag(SQLModel, table=True):
    """One (fiche, tag) pair, normalized out of `EtherItem.tags_json`.

    Supports cross-cutting tag navigation (e.g. "every kinésie tagged `fi`")
    that a JSON-blob column can't be queried against directly.
    """

    item_id: str = Field(primary_key=True, foreign_key='etheritem.id')
    tag: str = Field(primary_key=True, index=True)
