"""SQLModel tables for the stories runtime index — a disposable, rebuildable cache.

Same invariant as `ether.univers.index_models.EtherItem`: deleting `ether.db`
and re-running `ether index <project root>` must reproduce every row here
from the `stories/` markdown tree with zero data loss. The markdown files are
always the source of truth.

Unlike `EtherItem`, there is no accompanying link/tag table yet: `related`
can point at a univers fiche *or* another story node, and resolving that
correctly means looking across both `EtherItem` and `EtherStoryItem` — real
design work deferred to the browse-UI follow-up. For now `related_json` is
just stored, unresolved.
"""

from __future__ import annotations

from sqlmodel import Field
from sqlmodel import SQLModel


class EtherStoryItem(SQLModel, table=True):
    """One indexed story node: a saga/tome/act `_index.md`, a chapter, or an arc-narratif file."""

    id: str = Field(primary_key=True)
    type: str = Field(index=True)
    name: str = Field(index=True)
    saga: str = Field(default='', index=True)
    tome: str = Field(default='', index=True)
    status: str = Field(default='brouillon', index=True)
    aliases_json: str = Field(default='[]')
    tags_json: str = Field(default='[]')
    related_json: str = Field(default='[]')
    updated: str = Field(default='')
    relative_path: str
    body_excerpt: str = Field(default='')
    is_index: bool = Field(default=False, index=True)
    numero: int = Field(default=0)
    theme_specifique: str = Field(default='')
    question_centrale: str = Field(default='')
    fonction_narrative: str = Field(default='')
    etat_initial_protagoniste: str = Field(default='')
    etat_final_protagoniste: str = Field(default='')
    scope: str = Field(default='', index=True)
