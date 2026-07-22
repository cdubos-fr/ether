"""Prose generation for stories: context assembly + prompt rendering.

Replaces `ether.sequencer.redaction`: a chapter is now one markdown file
(frontmatter + body) instead of a DB `Chapitre`/`Partie` pair, so "the
previous scene" is just the tail of the chapter's own current body, and
approving a generated scene appends it behind a `***` break rather than
creating a new row.
"""

from __future__ import annotations

import json
from dataclasses import dataclass
from typing import TYPE_CHECKING

from sqlmodel import select

from ether.ai.backends import get_backend
from ether.ai.style_manifest import read_manifest
from ether.markdown_io import load_raw
from ether.markdown_io import write_file
from ether.stories import frontmatter
from ether.stories.index_models import EtherStoryItem
from ether.stories.indexer import reindex_one
from ether.templates import templates
from ether.univers.index_models import EtherItem

if TYPE_CHECKING:  # pragma: no cover
    from sqlmodel import Session

    from ether.config import EtherSettings

_BODY_TAIL_LENGTH = 600


class RedactionError(ValueError):
    """Raised when a redaction context cannot be assembled."""


@dataclass
class ContexteRedaction:
    """Everything the prompt needs to generate one scene's prose."""

    manifeste: str
    chapitre: EtherStoryItem
    fiches_liees: list[EtherItem]
    corps_actuel_tail: str
    instruction: str
    contraintes: str


def compose_redaction_context(
    session: Session,
    settings: EtherSettings,
    chapter_id: str,
    instruction: str,
    contraintes: str,
) -> ContexteRedaction:
    """Assemble everything needed to prompt for a chapter's next scene."""
    chapitre = session.get(EtherStoryItem, chapter_id)
    if chapitre is None:
        msg = f'Unknown chapter: {chapter_id}'
        raise RedactionError(msg)

    related_ids = json.loads(chapitre.related_json or '[]')
    fiches_liees: list[EtherItem] = []
    if related_ids:
        query = select(EtherItem).where(EtherItem.id.in_(related_ids))  # type: ignore[attr-defined]  # ty:ignore[unresolved-attribute]
        fiches_liees = list(session.exec(query))

    _, body = frontmatter.parse_file(settings.stories_path / chapitre.relative_path)
    tail = body.strip()[-_BODY_TAIL_LENGTH:]

    return ContexteRedaction(
        manifeste=read_manifest(settings.manifest_path_for(chapitre.saga)),
        chapitre=chapitre,
        fiches_liees=fiches_liees,
        corps_actuel_tail=tail,
        instruction=instruction,
        contraintes=contraintes,
    )


def render_prompt(ctx: ContexteRedaction) -> str:
    """Render the redaction prompt from a `ContexteRedaction` via Jinja2."""
    template = templates.get_template('stories/redaction_prompt.txt.j2')
    return template.render(ctx=ctx)


def generate_prose(prompt: str) -> str:
    """Call the configured AI backend to generate prose from `prompt`."""
    return get_backend().generate(prompt)


def append_scene(
    settings: EtherSettings,
    chapitre: EtherStoryItem,
    draft: str,
    session: Session,
) -> None:
    """Append an approved scene draft to the chapter's body behind a `***` break."""
    path = settings.stories_path / chapitre.relative_path
    raw, body = load_raw(path)
    body = body.strip()
    draft = draft.strip()
    new_body = f'{body}\n\n***\n\n{draft}\n' if body else f'{draft}\n'
    write_file(path, raw, new_body)
    reindex_one(
        settings.stories_path,
        chapitre.relative_path,
        chapitre.saga,
        chapitre.tome,
        session,
    )
