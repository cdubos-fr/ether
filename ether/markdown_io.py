"""Generic markdown-with-YAML-frontmatter file I/O, shared by every fiche domain.

Extracted from `ether.univers.frontmatter` so `ether.stories` can share the
same atomic-write/round-trip YAML implementation without reaching into a
sibling feature package. Nothing here knows about `FicheFrontmatter` or any
other domain-specific shape — see `ether.univers.frontmatter` and
`ether.stories.frontmatter` for the schema-aware layer built on top.
"""

from __future__ import annotations

import datetime as dt
import io
import os
import tempfile
from pathlib import Path
from typing import TYPE_CHECKING
from typing import Any

from ruamel.yaml import YAML
from ruamel.yaml.comments import CommentedSeq

if TYPE_CHECKING:  # pragma: no cover
    from collections.abc import Mapping

_FENCE = '---'

_yaml = YAML()
_yaml.preserve_quotes = True
_yaml.width = 4096


class FrontmatterError(ValueError):
    """Raised when a markdown file does not have a well-formed frontmatter block."""


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


def load_yaml_block(yaml_block: str) -> Any:  # noqa: ANN401 - mirrors `load_raw`'s untyped ruamel mapping
    """Parse a raw YAML frontmatter block (as split off by `split_frontmatter`)."""
    data = _yaml.load(yaml_block)
    return data if data is not None else {}


def load_raw(path: Path) -> tuple[Any, str]:
    """Read a markdown file, returning its ruamel-loaded frontmatter mapping and body.

    The returned mapping is a `CommentedMap`: mutate it in place and pass it
    back to `write_file` to preserve key order and formatting for fields you
    didn't touch.
    """
    text = path.read_text(encoding='utf-8')
    yaml_block, body = split_frontmatter(text)
    return load_yaml_block(yaml_block), body


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
