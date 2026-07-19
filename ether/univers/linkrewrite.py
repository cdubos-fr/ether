"""Rewrite relative markdown-file links in fiche prose to `/item/{id}` routes.

The univers repo's own convention (see `saga-eveil-univers/README.md`) is
plain relative markdown links in prose — `[Alice](../../personnages/.../
alice.md)` — deliberately *not* wikilinks, so the repo stays readable by any
tool or script outside ether. But ether serves fiches at `/item/{id}`, not at
their file path, so those links 404 as-is inside the app.

This rewrites them purely for display: it operates on the raw markdown text
right before HTML conversion and never touches the source files. Links that
don't resolve to a currently-indexed fiche (dangling, or pointing outside the
univers repo) are left exactly as written.
"""

from __future__ import annotations

import posixpath
import re
from typing import TYPE_CHECKING

if TYPE_CHECKING:  # pragma: no cover
    from collections.abc import Mapping
    from pathlib import Path

_MD_LINK_RE = re.compile(
    r'(?P<bang>!?)\[(?P<text>[^\[\]]*)\]\((?P<path>[^()\s]+\.md)(?P<fragment>#[^()\s]*)?\)',
)


def rewrite_relative_links(
    body: str,
    current_relative_path: Path,
    path_to_id: Mapping[str, str],
) -> str:
    """Rewrite `[text](relative/path.md)` links to `/item/{id}` where resolvable.

    `current_relative_path` is the fiche's own path within the univers repo
    (used as the base for resolving `../`-relative targets); `path_to_id`
    maps every indexed fiche's relative path to its id (see
    `ether.univers.indexer.path_index`). Images (`![...](...)`) are left
    alone — a `.md` image target would be unusual, but matching the `!`
    keeps this from ever misfiring on one.
    """
    base = current_relative_path.parent

    def _replace(match: re.Match[str]) -> str:
        if match.group('bang'):
            return match.group(0)
        target = posixpath.normpath(posixpath.join(str(base), match.group('path')))
        item_id = path_to_id.get(target)
        if item_id is None:
            return match.group(0)
        fragment = match.group('fragment') or ''
        return f'[{match.group("text")}](/item/{item_id}{fragment})'

    return _MD_LINK_RE.sub(_replace, body)
