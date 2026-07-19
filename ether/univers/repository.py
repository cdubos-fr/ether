"""Read/write access to individual fiches on disk.

All edits land on the markdown itself (see the module docstring in
`ether/univers/index_models.py` for why the DB is never authoritative). Two
granularities are supported: overwriting a whole fiche (`write_item`) and
patching a single `##` section within one (`write_section`), so small changes
don't have to rewrite an entire file.
"""

from __future__ import annotations

import re
from typing import TYPE_CHECKING
from typing import Any

from filelock import FileLock

from ether.univers import frontmatter
from ether.univers.scanner import find_template

if TYPE_CHECKING:  # pragma: no cover
    from pathlib import Path

    from ether.univers.schema import FicheFrontmatter

_SECTION_HEADING_RE = re.compile(r'^##\s+(?P<heading>.+?)\s*$', re.MULTILINE)


def _lock_path(root: Path) -> Path:
    lock_dir = root / '.ether'
    lock_dir.mkdir(exist_ok=True)
    return lock_dir / 'index.lock'


def repo_lock(root: Path) -> FileLock:
    """File lock guarding a full reindex against concurrent single-file writes."""
    return FileLock(str(_lock_path(root)))


def _apply_meta(raw: dict[str, Any], meta: FicheFrontmatter) -> None:
    # `raw` is an existing file's loaded YAML mapping (see
    # `frontmatter.FrontmatterMapping`'s docstring): it may carry extra,
    # author-defined keys beyond our fixed schema, which a TypedDict can't
    # express, so this stays a plain `dict[str, Any]` rather than one.
    raw['id'] = meta.id
    raw['type'] = meta.type
    raw['name'] = meta.name
    raw['aliases'] = frontmatter.flow_seq(raw.get('aliases'), list(meta.aliases))
    raw['status'] = meta.status
    raw['tags'] = frontmatter.flow_seq(raw.get('tags'), list(meta.tags))
    raw['related'] = frontmatter.flow_seq(raw.get('related'), list(meta.related))
    raw['updated'] = frontmatter.coerce_date(meta.updated)


def write_item(root: Path, relative_path: str, meta: FicheFrontmatter, body: str) -> None:
    """Overwrite a fiche's frontmatter + body.

    If the file already exists, its YAML mapping is loaded and mutated in
    place so key order/quoting of untouched fields survives; a brand-new file
    gets a fresh mapping in the repo's conventional field order.
    """
    path = root / relative_path
    with repo_lock(root):
        if path.is_file():
            raw, _old_body = frontmatter.load_raw(path)
            _apply_meta(raw, meta)
            frontmatter.write_file(path, raw, body)
        else:
            frontmatter.write_file(path, frontmatter.new_frontmatter_mapping(meta), body)


def list_sections(body: str) -> list[str]:
    """List the `##` section headings present in a fiche body, in order."""
    return [m.group('heading') for m in _SECTION_HEADING_RE.finditer(body)]


def _patch_section(body: str, heading: str, content: str, mode: str) -> str:
    pattern = re.compile(
        rf'^##\s+{re.escape(heading)}\s*\n(.*?)(?=^## |\Z)',
        re.MULTILINE | re.DOTALL,
    )
    heading_line = f'## {heading}'
    match = pattern.search(body)
    if match is None:
        prefix = f'{body.rstrip()}\n\n' if body.strip() else ''
        return f'{prefix}{heading_line}\n\n{content.strip()}\n'
    if mode == 'append':
        existing = match.group(1).strip()
        merged = f'{existing}\n\n{content.strip()}' if existing else content.strip()
    else:
        merged = content.strip()
    return body[: match.start()] + f'{heading_line}\n\n{merged}\n\n' + body[match.end() :]


def write_section(
    root: Path,
    relative_path: str,
    heading: str,
    content: str,
    mode: str = 'replace',
) -> None:
    """Replace or append a `##`-heading section within an existing fiche's body.

    `mode='replace'` overwrites the section's content (up to the next `##`
    heading or end of file, creating the section if it doesn't exist yet);
    `mode='append'` adds to the section's existing content instead.
    """
    path = root / relative_path
    with repo_lock(root):
        raw, body = frontmatter.load_raw(path)
        new_body = _patch_section(body, heading, content, mode)
        frontmatter.write_file(path, raw, new_body)


def expected_sections(root: Path, category: str) -> list[str]:
    """Section headings suggested by a category's `_template.md`, if any.

    Used both to offer section names in the edit UI and as the skeleton for
    AI-assisted creation (phase 3).
    """
    template_path = find_template(root, category)
    if template_path is None:
        return []
    text = template_path.read_text(encoding='utf-8')
    fence_match = re.search(r'```markdown\n(.*?)```', text, re.DOTALL)
    sample = fence_match.group(1) if fence_match else text
    return list_sections(sample)
