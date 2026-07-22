"""Parse and write story nodes: a `StoryFrontmatter` schema over `ether.markdown_io`.

Mirrors `ether.univers.frontmatter` field for field, adding the extra
optional planning fields `StoryFrontmatter` carries. See that module and
`ether.markdown_io` for why the generic mechanics live separately.
"""

from __future__ import annotations

from typing import TYPE_CHECKING
from typing import TypedDict

from ether.markdown_io import FrontmatterError
from ether.markdown_io import coerce_date
from ether.markdown_io import flow_seq
from ether.markdown_io import load_raw
from ether.markdown_io import load_yaml_block
from ether.markdown_io import split_frontmatter
from ether.markdown_io import write_file
from ether.stories.schema import StoryFrontmatter

if TYPE_CHECKING:  # pragma: no cover
    import datetime as dt
    from collections.abc import Mapping
    from pathlib import Path
    from typing import Any

    from ruamel.yaml.comments import CommentedSeq

__all__ = [
    'FrontmatterError',
    'StoryFrontmatterMapping',
    'coerce_date',
    'flow_seq',
    'load_raw',
    'new_story_frontmatter_mapping',
    'parse_file',
    'parse_text',
    'split_frontmatter',
    'to_story_frontmatter',
    'write_file',
]


def to_story_frontmatter(data: Mapping[str, Any]) -> StoryFrontmatter:
    """Coerce a raw YAML mapping into a validated `StoryFrontmatter`."""
    missing = [key for key in ('id', 'type', 'name') if key not in data]
    if missing:
        msg = f'missing required frontmatter field(s): {", ".join(missing)}'
        raise FrontmatterError(msg)
    return StoryFrontmatter(
        id=str(data['id']),
        type=str(data['type']),
        name=str(data['name']),
        aliases=list(data.get('aliases') or []),
        status=str(data.get('status', 'brouillon')),
        tags=list(data.get('tags') or []),
        related=list(data.get('related') or []),
        updated=str(data.get('updated', '')),
        numero=int(data.get('numero', 0) or 0),
        theme_specifique=str(data.get('theme_specifique', '')),
        question_centrale=str(data.get('question_centrale', '')),
        fonction_narrative=str(data.get('fonction_narrative', '')),
        etat_initial_protagoniste=str(data.get('etat_initial_protagoniste', '')),
        etat_final_protagoniste=str(data.get('etat_final_protagoniste', '')),
    )


def parse_text(text: str) -> tuple[StoryFrontmatter, str]:
    """Parse frontmatter + body from raw markdown text (not necessarily on disk yet)."""
    yaml_block, body = split_frontmatter(text)
    return to_story_frontmatter(load_yaml_block(yaml_block)), body


def parse_file(path: Path) -> tuple[StoryFrontmatter, str]:
    """Read a markdown file and return its validated frontmatter and body."""
    raw, body = load_raw(path)
    return to_story_frontmatter(raw), body


class StoryFrontmatterMapping(TypedDict):
    """The fixed frontmatter shape for a brand-new story node, in field order.

    See `ether.univers.frontmatter.FrontmatterMapping` for why this stays
    separate from the more permissive `Mapping[str, Any]` used for round-tripping
    an existing, possibly hand-edited file.
    """

    id: str
    type: str
    name: str
    aliases: CommentedSeq
    status: str
    tags: CommentedSeq
    related: CommentedSeq
    updated: dt.date | str
    numero: int
    theme_specifique: str
    question_centrale: str
    fonction_narrative: str
    etat_initial_protagoniste: str
    etat_final_protagoniste: str


def new_story_frontmatter_mapping(meta: StoryFrontmatter) -> StoryFrontmatterMapping:
    """Build a fresh frontmatter mapping in the repo's conventional field order.

    Only used for brand-new story nodes, which have no prior formatting to preserve.
    """
    return StoryFrontmatterMapping(
        id=meta.id,
        type=meta.type,
        name=meta.name,
        aliases=flow_seq(None, list(meta.aliases)),
        status=meta.status,
        tags=flow_seq(None, list(meta.tags)),
        related=flow_seq(None, list(meta.related)),
        updated=coerce_date(meta.updated),
        numero=meta.numero,
        theme_specifique=meta.theme_specifique,
        question_centrale=meta.question_centrale,
        fonction_narrative=meta.fonction_narrative,
        etat_initial_protagoniste=meta.etat_initial_protagoniste,
        etat_final_protagoniste=meta.etat_final_protagoniste,
    )
