"""Generic frontmatter schema shared by every story node (saga/tome/act/chapter).

One shape covers every level of the stories tree, the same way
`ether.univers.schema.FicheFrontmatter` covers every univers fiche `type` —
the base fields (`id, type, name, aliases, status, tags, related, updated`)
are identical to a univers fiche's, plus a handful of planning fields that
are simply left blank at levels they don't apply to (e.g. a chapter's
`theme_specifique` is unused; a tome's `etat_initial_protagoniste` is unused).

Kept as its own dataclass rather than reusing `FicheFrontmatter` directly so
the univers schema doesn't have to carry story-planning concepts it has no
use for — see `ether.univers.schema`'s own docstring on that module's scope.
"""

from __future__ import annotations

from dataclasses import dataclass
from dataclasses import field


@dataclass
class StoryFrontmatter:
    """Parsed and validated YAML frontmatter of a single story node."""

    id: str
    type: str
    name: str
    aliases: list[str] = field(default_factory=list)
    status: str = 'brouillon'
    tags: list[str] = field(default_factory=list)
    related: list[str] = field(default_factory=list)
    updated: str = ''
    numero: int = 0
    theme_specifique: str = ''
    question_centrale: str = ''
    fonction_narrative: str = ''
    etat_initial_protagoniste: str = ''
    etat_final_protagoniste: str = ''
