"""Prose generation for the sequencer: context assembly + prompt rendering.

Adapted from `studio-conception-narrative`'s `context_builder.py`/
`redaction_engine.py`, but pulling relevant fiches from the univers link graph
(`Chapitre.fiches_liees_json`) instead of a DB-only Codex.
"""

from __future__ import annotations

import json
from dataclasses import dataclass
from typing import TYPE_CHECKING

from sqlmodel import select

from ether.ai.backends import get_backend
from ether.ai.style_manifest import read_manifest
from ether.sequencer.models import Chapitre
from ether.sequencer.models import Partie
from ether.templates import templates
from ether.univers.index_models import EtherItem

if TYPE_CHECKING:  # pragma: no cover
    from sqlmodel import Session

    from ether.config import EtherSettings


class RedactionError(ValueError):
    """Raised when a redaction context cannot be assembled."""


@dataclass
class ContexteRedaction:
    """Everything the prompt needs to generate one scene's prose."""

    manifeste: str
    chapitre: Chapitre
    fiches_liees: list[EtherItem]
    scenes_precedentes: list[str]
    instruction: str
    contraintes: str


def compose_redaction_context(
    session: Session,
    settings: EtherSettings,
    chapitre_id: int,
    partie_id: int | None,
    instruction: str,
    contraintes: str,
) -> ContexteRedaction:
    """Assemble everything needed to prompt for one scene's prose."""
    chapitre = session.get(Chapitre, chapitre_id)
    if chapitre is None:
        msg = f'Unknown chapitre: {chapitre_id}'
        raise RedactionError(msg)

    fiche_ids = json.loads(chapitre.fiches_liees_json or '[]')
    fiches_liees: list[EtherItem] = []
    if fiche_ids:
        query = select(EtherItem).where(EtherItem.id.in_(fiche_ids))  # type: ignore[attr-defined]  # ty:ignore[unresolved-attribute]
        fiches_liees = list(session.exec(query))

    scenes_precedentes: list[str] = []
    if partie_id is not None:
        parties = sorted(
            session.exec(select(Partie).where(Partie.chapitre_id == chapitre_id)),
            key=lambda p: (p.numero, p.id or 0),
        )
        for partie in parties:
            if partie.id == partie_id:
                break
            if partie.statut == 'Validé' and partie.contenu_genere:
                excerpt = partie.contenu_genere[:400].strip()
                scenes_precedentes.append(f'[Scène {partie.numero}] {excerpt}')
        scenes_precedentes = scenes_precedentes[-2:]

    return ContexteRedaction(
        manifeste=read_manifest(settings.style_manifest_path),
        chapitre=chapitre,
        fiches_liees=fiches_liees,
        scenes_precedentes=scenes_precedentes,
        instruction=instruction,
        contraintes=contraintes,
    )


def render_prompt(ctx: ContexteRedaction) -> str:
    """Render the redaction prompt from a `ContexteRedaction` via Jinja2."""
    template = templates.get_template('redaction/prompt.txt.j2')
    return template.render(ctx=ctx)


def generate_prose(prompt: str) -> str:
    """Call the configured AI backend to generate prose from `prompt`."""
    return get_backend().generate(prompt)
