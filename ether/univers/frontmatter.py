"""Parse and write markdown files with YAML frontmatter.

Existing files are round-tripped through `ruamel.yaml` in round-trip mode so
that editing a handful of fields does not reorder or reformat the rest of the
frontmatter block: the univers repo is git-tracked and diffs should stay
minimal (see `load_raw`/`write_file`).
"""

from __future__ import annotations

import datetime as dt
import io
import os
import tempfile
from pathlib import Path
from typing import TYPE_CHECKING
from typing import Any
from typing import TypedDict

from ruamel.yaml import YAML
from ruamel.yaml.comments import CommentedSeq

from ether.univers.schema import FicheFrontmatter

if TYPE_CHECKING:  # pragma: no cover
    from collections.abc import Mapping

_FENCE = '---'

_yaml = YAML()
_yaml.preserve_quotes = True
_yaml.width = 4096


def coerce_date(value: str) -> dt.date | str:
    """Turn an ISO date string back into a native date for unquoted YAML output.

    Matches this repo convention's `updated: 2026-07-18` (unquoted): a plain
    Python `str` would otherwise get dumped quoted (`'2026-07-18'`) to avoid
    being re-interpreted as a date on the next load, which is a needless
    formatting diff.
    """
    try:
        return dt.date.fromisoformat(value)
    except ValueError:
        return value


def flow_seq(existing: object, values: list[str]) -> CommentedSeq:
    """Build/update a flow-style (`[a, b]`) YAML sequence for `values`.

    `existing` is typed `object`, not `CommentedSeq | None`: it comes from
    `raw.get(key)` on a freshly YAML-loaded, not-yet-validated mapping, so it
    could in principle be any scalar a hand-edited file put there. The
    `isinstance` check below is exactly what makes that safe.

    Mutates `existing` in place when it's already a `CommentedSeq` so its flow
    style survives; otherwise builds a fresh flow-style sequence, matching this
    repo convention's `aliases/tags/related: [...]` style.
    """
    if isinstance(existing, CommentedSeq):
        existing.clear()
        existing.extend(values)
        return existing
    seq = CommentedSeq(values)
    seq.fa.set_flow_style()
    return seq


class FrontmatterError(ValueError):
    """Raised when a markdown file does not have a well-formed frontmatter block."""


def split_frontmatter(text: str) -> tuple[str, str]:
    """Split raw file text into (yaml_block, body)."""
    if not text.startswith(_FENCE):
        msg = 'file does not start with a YAML frontmatter fence (---)'
        raise FrontmatterError(msg)
    end = text.find(f'\n{_FENCE}', len(_FENCE))
    if end == -1:
        msg = 'unterminated YAML frontmatter block'
        raise FrontmatterError(msg)
    yaml_block = text[len(_FENCE) : end]
    body = text[end + len(f'\n{_FENCE}') :]
    return yaml_block, body.lstrip('\n')


def load_raw(path: Path) -> tuple[Any, str]:
    """Read a markdown file, returning its ruamel-loaded frontmatter mapping and body.

    The returned mapping is a `CommentedMap`: mutate it in place and pass it
    back to `write_file` to preserve key order and formatting for fields you
    didn't touch.
    """
    text = path.read_text(encoding='utf-8')
    yaml_block, body = split_frontmatter(text)
    data = _yaml.load(yaml_block)
    return (data if data is not None else {}), body


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
    data = _yaml.load(yaml_block)
    return to_frontmatter(data if data is not None else {}), body


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


def _atomic_write(path: Path, content: str) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    fd, tmp_name = tempfile.mkstemp(dir=str(path.parent), prefix=f'.{path.name}.', suffix='.tmp')
    try:
        with os.fdopen(fd, 'w', encoding='utf-8') as fh:
            fh.write(content)
        os.replace(tmp_name, path)
    except BaseException:
        Path(tmp_name).unlink(missing_ok=True)
        raise


def write_file(path: Path, data: Mapping[str, Any], body: str) -> None:
    """Atomically (over)write a markdown file's frontmatter + body block."""
    buf = io.StringIO()
    _yaml.dump(data, buf)
    yaml_text = buf.getvalue().rstrip('\n')
    content = f'{_FENCE}\n{yaml_text}\n{_FENCE}\n\n{body.strip()}\n'
    _atomic_write(path, content)
