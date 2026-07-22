"""Parse and write univers fiches: a `FicheFrontmatter` schema over `ether.markdown_io`.

The generic markdown-with-YAML-frontmatter mechanics (splitting, atomic
writes, round-trip YAML) live in `ether.markdown_io`, shared with
`ether.stories`; this module only adds the univers-specific `FicheFrontmatter`
shape on top.
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
from ether.univers.schema import FicheFrontmatter

if TYPE_CHECKING:  # pragma: no cover
    import datetime as dt
    from collections.abc import Mapping
    from pathlib import Path
    from typing import Any

    from ruamel.yaml.comments import CommentedSeq

__all__ = [
    'FrontmatterError',
    'FrontmatterMapping',
    'coerce_date',
    'flow_seq',
    'load_raw',
    'new_frontmatter_mapping',
    'parse_file',
    'parse_text',
    'split_frontmatter',
    'to_frontmatter',
    'write_file',
]


def to_frontmatter(data: Mapping[str, Any]) -> FicheFrontmatter:
    """Coerce a raw YAML mapping into a validated `FicheFrontmatter`."""
    missing = [key for key in ('id', 'type', 'name') if key not in data]
    if missing:
        msg = f'missing required frontmatter field(s): {", ".join(missing)}'
        raise FrontmatterError(msg)
    return FicheFrontmatter(
        id=str(data['id']),
        type=str(data['type']),
        name=str(data['name']),
        aliases=list(data.get('aliases') or []),
        status=str(data.get('status', 'brouillon')),
        tags=list(data.get('tags') or []),
        related=list(data.get('related') or []),
        updated=str(data.get('updated', '')),
    )


def parse_text(text: str) -> tuple[FicheFrontmatter, str]:
    """Parse frontmatter + body from raw markdown text (not necessarily on disk yet)."""
    yaml_block, body = split_frontmatter(text)
    return to_frontmatter(load_yaml_block(yaml_block)), body


def parse_file(path: Path) -> tuple[FicheFrontmatter, str]:
    """Read a markdown file and return its validated frontmatter and body."""
    raw, body = load_raw(path)
    return to_frontmatter(raw), body


class FrontmatterMapping(TypedDict):
    """The repo's fixed frontmatter shape, in its conventional field order.

    Only describes brand-new fiches (see `new_frontmatter_mapping`): an
    *existing* file's mapping may carry additional author-defined keys
    beyond this fixed set (frontmatter isn't a closed schema — see the
    module docstring on preserving unknown fields), which is exactly why
    `load_raw`/`write_file` still deal in the more permissive
    `Mapping[str, Any]` rather than this TypedDict — there's no way to
    express "these known keys, plus arbitrary extra ones" with TypedDict.
    """

    id: str
    type: str
    name: str
    aliases: CommentedSeq
    status: str
    tags: CommentedSeq
    related: CommentedSeq
    updated: dt.date | str


def new_frontmatter_mapping(meta: FicheFrontmatter) -> FrontmatterMapping:
    """Build a fresh frontmatter mapping in the repo's conventional field order.

    Only used for brand-new fiches, which have no prior formatting to preserve.
    """
    return FrontmatterMapping(
        id=meta.id,
        type=meta.type,
        name=meta.name,
        aliases=flow_seq(None, list(meta.aliases)),
        status=meta.status,
        tags=flow_seq(None, list(meta.tags)),
        related=flow_seq(None, list(meta.related)),
        updated=coerce_date(meta.updated),
    )
