"""Walk a univers repository and yield the markdown fiches it contains."""

from __future__ import annotations

import re
from dataclasses import dataclass
from typing import TYPE_CHECKING

from ether.univers.frontmatter import FrontmatterError
from ether.univers.frontmatter import parse_file

if TYPE_CHECKING:  # pragma: no cover
    from collections.abc import Iterator
    from pathlib import Path

    from ether.univers.schema import FicheFrontmatter

_SPECIAL_STEMS = {'_template', '_manifest'}
INDEX_STEM = '_index'


@dataclass
class RawFiche:
    """A single content fiche discovered on disk, with its parsed frontmatter."""

    meta: FicheFrontmatter
    body: str
    path: Path
    relative_path: Path
    is_index: bool = False


@dataclass
class ScanIssue:
    """A markdown file that could not be parsed as a fiche."""

    path: Path
    error: str


@dataclass
class ScanResult:
    """Outcome of walking a univers repository."""

    fiches: list[RawFiche]
    issues: list[ScanIssue]


def _iter_markdown_files(root: Path) -> Iterator[Path]:
    for path in sorted(root.rglob('*.md')):
        if path.stem in _SPECIAL_STEMS:
            continue
        yield path


def walk_repo(root: Path) -> ScanResult:
    """Walk `root` for content fiches, skipping `_template.md` and `_manifest.md`.

    `_index.md` files ARE indexed: in practice they often double as the
    fiche for the folder itself (e.g. `organisations/le-concile/_index.md`
    is the actual "Le Concile" fiche, not just a navigation table), and other
    fiches legitimately reference them via `related`. See `RawFiche.is_index`.
    """
    fiches: list[RawFiche] = []
    issues: list[ScanIssue] = []
    for path in _iter_markdown_files(root):
        try:
            meta, body = parse_file(path)
        except FrontmatterError as exc:
            issues.append(ScanIssue(path=path, error=str(exc)))
            continue
        relative_path = path.relative_to(root)
        fiches.append(
            RawFiche(
                meta=meta,
                body=body,
                path=path,
                relative_path=relative_path,
                is_index=relative_path.stem == INDEX_STEM,
            ),
        )
    return ScanResult(fiches=fiches, issues=issues)


def find_template(root: Path, category: str) -> Path | None:
    """Return the `_template.md` for a category folder, if any."""
    candidate = root / category / '_template.md'
    return candidate if candidate.is_file() else None


def read_template_skeleton(template_path: Path) -> str:
    """Extract the fenced frontmatter + body skeleton from a `_template.md`.

    `_template.md` files are documentation *about* the template, with the
    actual copy-me skeleton embedded in ` ```yaml ` and ` ```markdown ` code
    fences (see the real example at `saga-eveil-univers`) — this pulls just
    that skeleton out, for feeding to an AI backend or offering as a starting
    point in the creation panel.
    """
    text = template_path.read_text(encoding='utf-8')
    yaml_match = re.search(r'```yaml\n(.*?)```', text, re.DOTALL)
    md_match = re.search(r'```markdown\n(.*?)```', text, re.DOTALL)
    parts = [m.group(1).strip() for m in (yaml_match, md_match) if m]
    return '\n\n'.join(parts) if parts else text


def find_index(root: Path, category: str) -> Path | None:
    """Return the `_index.md` for a category folder, if any."""
    candidate = root / category / '_index.md'
    return candidate if candidate.is_file() else None


def list_categories(root: Path) -> list[str]:
    """List top-level folders under `root` that contain at least one markdown file."""
    categories: set[str] = set()
    for path in root.rglob('*.md'):
        rel = path.relative_to(root)
        if len(rel.parts) > 1:
            categories.add(rel.parts[0])
    return sorted(categories)
