"""Generic frontmatter schema shared by every fiche in a univers repository.

These field names are the only structural assumption ether makes about a
univers repo's content. `type` values, folder names and domain vocabulary are
free text supplied by the repo itself and are never hardcoded here — this is
what lets ether work unmodified against any universe that follows the same
generic conventions (see the real example at `saga-eveil-univers`).
"""

from __future__ import annotations

from dataclasses import dataclass
from dataclasses import field


@dataclass
class FicheFrontmatter:
    """Parsed and validated YAML frontmatter of a single fiche."""

    id: str
    type: str
    name: str
    aliases: list[str] = field(default_factory=list)
    status: str = 'brouillon'
    tags: list[str] = field(default_factory=list)
    related: list[str] = field(default_factory=list)
    updated: str = ''
