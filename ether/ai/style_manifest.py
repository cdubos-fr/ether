"""The author's style manifesto: tone, intention, and prose rules.

Stored as a plain markdown file (not a DB row) alongside the univers repo, so
it stays git-diffable and portable with the project — see the module
docstring on `ether.univers.index_models` for why the DB never holds
authoritative content.

The *shape* is fixed and shipped by ether (`StyleManifestForm`, one field per
section, two of which — "Point de vue & voix narrative" and "Règles de
prose" — are editable lists rather than free text); the fill-in is 100%
author voice. The web UI (`ether.web.routers.style`) edits the structured
form; on disk it's still plain markdown, and `read_manifest` (used by
`ether.ai.prompt_builder`) still just returns that text verbatim.
"""

from __future__ import annotations

import datetime as dt
import re
from dataclasses import dataclass
from dataclasses import field
from typing import TYPE_CHECKING

from ether.univers.frontmatter import FrontmatterError
from ether.univers.frontmatter import split_frontmatter

if TYPE_CHECKING:  # pragma: no cover
    from pathlib import Path

HEADINGS = {
    'intention_thematique': 'Intention thématique',
    'point_de_vue': 'Point de vue & voix narrative',
    'registre_ton': 'Registre & ton',
    'regles_prose': 'Règles de prose',
    'a_eviter': 'À éviter',
    'format_sortie': 'Format de sortie',
}

_HEADING_RE = re.compile(r'^##\s+(.+?)\s*$', re.MULTILINE)
_BULLET_RE = re.compile(r'^-\s*(?:\*\*(?P<label>.+?)\*\*\s*)?(?P<content>.*)$')
_TITLE_RE = re.compile(r"^#\s+Manifeste d'écriture\s*(?:—|-)?\s*(.*)$", re.MULTILINE)
_UPDATED_RE = re.compile(r'^updated:\s*(.+)$', re.MULTILINE)


@dataclass
class ManifestRule:
    """One labeled bullet within a list-shaped manifest section."""

    label: str = ''
    content: str = ''


@dataclass
class StyleManifestForm:
    """The manifest's fixed shape, split into one editable field per section."""

    project_name: str = ''
    updated: str = ''
    intention_thematique: str = ''
    point_de_vue: list[ManifestRule] = field(default_factory=list)
    registre_ton: str = ''
    regles_prose: list[ManifestRule] = field(default_factory=list)
    a_eviter: str = ''
    format_sortie: str = ''


def default_form(project_name: str) -> StyleManifestForm:
    """Build the seed content offered for a brand-new manifest."""
    return StyleManifestForm(
        project_name=project_name,
        updated=dt.date.today().isoformat(),
        intention_thematique=(
            'Le/les thèmes centraux que toute scène doit servir. '
            'Test : "en quoi cette scène sert ce thème ?"'
        ),
        point_de_vue=[
            ManifestRule('Personne / temps', 'ex. première personne, présent'),
            ManifestRule(
                'Filtre de conscience',
                'à qui appartient le regard ; ce qui est interdit hors de ce filtre',
            ),
            ManifestRule(
                'Monologue intérieur',
                'priorité relative pensée brute vs action/description extérieure',
            ),
        ],
        registre_ton="formel/familier, sombre/léger, niveau d'humour, distance émotionnelle",
        regles_prose=[
            ManifestRule(
                'Filtre sensoriel',
                "ex. pas d'abstraction émotionnelle nommée ; sensation avant analyse",
            ),
            ManifestRule(
                'Rythme',
                'dilatation/compression du temps ; longueur de phrase selon intensité',
            ),
            ManifestRule(
                'Dialogue',
                "formatage, fonction de chaque réplique, interdiction de l'exposition gratuite",
            ),
        ],
        a_eviter='Tics de langage, clichés, procédés bannis pour cet auteur/projet.',
        format_sortie='markdown : emphase, ponctuation du dialogue, marqueurs de saut de scène.',
    )


def _render_rules(rules: list[ManifestRule]) -> str:
    lines = [
        f'- **{rule.label} :** {rule.content}' if rule.label else f'- {rule.content}'
        for rule in rules
        if rule.label.strip() or rule.content.strip()
    ]
    return '\n'.join(lines) if lines else '_(aucune)_'


def _parse_rules(text: str) -> list[ManifestRule]:
    rules = []
    for raw_line in text.splitlines():
        line = raw_line.strip()
        if not line.startswith('-'):
            continue
        match = _BULLET_RE.match(line)
        if match is None:
            continue
        label = (match.group('label') or '').strip().rstrip(':').strip()
        rules.append(ManifestRule(label=label, content=match.group('content').strip()))
    return rules


def _split_sections(body: str) -> dict[str, str]:
    """Map `##` heading -> its raw section text (up to the next heading)."""
    matches = list(_HEADING_RE.finditer(body))
    sections: dict[str, str] = {}
    for index, match in enumerate(matches):
        start = match.end()
        end = matches[index + 1].start() if index + 1 < len(matches) else len(body)
        sections[match.group(1).strip()] = body[start:end].strip()
    return sections


def render_markdown(form: StyleManifestForm) -> str:
    """Serialize a form back into the manifest's fixed markdown shape."""
    sections = [
        f'---\nupdated: {form.updated or dt.date.today().isoformat()}\n---',
        f"# Manifeste d'écriture — {form.project_name}",
        f'## {HEADINGS["intention_thematique"]}\n\n{form.intention_thematique.strip()}',
        f'## {HEADINGS["point_de_vue"]}\n\n{_render_rules(form.point_de_vue)}',
        f'## {HEADINGS["registre_ton"]}\n\n{form.registre_ton.strip()}',
        f'## {HEADINGS["regles_prose"]}\n\n{_render_rules(form.regles_prose)}',
        f'## {HEADINGS["a_eviter"]}\n\n{form.a_eviter.strip()}',
        f'## {HEADINGS["format_sortie"]}\n\n{form.format_sortie.strip()}',
    ]
    return '\n\n'.join(sections) + '\n'


def parse_markdown(text: str, fallback_project_name: str) -> StyleManifestForm:
    """Best-effort parse an existing manifest file back into a `StyleManifestForm`.

    Tolerant of content that doesn't fully match the expected shape (e.g. a
    manually-edited manifest, or one predating the structured-form editor):
    missing sections simply come back empty rather than raising.
    """
    if not text.strip():
        return default_form(fallback_project_name)

    try:
        yaml_block, body = split_frontmatter(text)
    except FrontmatterError:
        yaml_block, body = '', text

    title_match = _TITLE_RE.search(body)
    project_name = title_match.group(1).strip() if title_match else fallback_project_name

    updated_match = _UPDATED_RE.search(yaml_block)
    updated = updated_match.group(1).strip().strip('\'"') if updated_match else ''

    sections = _split_sections(body)
    return StyleManifestForm(
        project_name=project_name or fallback_project_name,
        updated=updated,
        intention_thematique=sections.get(HEADINGS['intention_thematique'], ''),
        point_de_vue=_parse_rules(sections.get(HEADINGS['point_de_vue'], '')),
        registre_ton=sections.get(HEADINGS['registre_ton'], ''),
        regles_prose=_parse_rules(sections.get(HEADINGS['regles_prose'], '')),
        a_eviter=sections.get(HEADINGS['a_eviter'], ''),
        format_sortie=sections.get(HEADINGS['format_sortie'], ''),
    )


def read_manifest(path: Path) -> str:
    """Read the project's style manifest, or '' if none has been scaffolded yet."""
    if not path.is_file():
        return ''
    return path.read_text(encoding='utf-8')


def ensure_manifest(path: Path, project_name: str) -> Path:
    """Scaffold the manifest from the default form if it doesn't exist yet."""
    if not path.is_file():
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(render_markdown(default_form(project_name)), encoding='utf-8')
    return path


def write_manifest(path: Path, text: str) -> None:
    """Overwrite the style manifest with the (structured-form-rendered) text."""
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(text, encoding='utf-8')
