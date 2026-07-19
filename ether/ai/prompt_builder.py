"""Assemble LLM prompts for AI-assisted creation and redaction.

Pure string assembly: callers resolve the manifest text, template skeleton,
and existing items themselves (see `ether.web.routers.create`), which keeps
this module trivially testable without touching disk or the DB.
"""

from __future__ import annotations

from typing import TYPE_CHECKING

if TYPE_CHECKING:  # pragma: no cover
    from collections.abc import Sequence

    from ether.univers.index_models import EtherItem

_NO_MANIFEST = '(aucun manifeste défini)'


def compose_item_context(
    manifest_text: str,
    template_skeleton: str,
    brief: str,
    existing_items: Sequence[EtherItem],
) -> str:
    """Build the prompt asking the backend to draft a brand-new fiche."""
    existing = '\n'.join(f'- {item.id}: {item.name} ({item.type})' for item in existing_items[:40])
    sections = [
        '[MANIFESTE DE STYLE]',
        manifest_text or _NO_MANIFEST,
        '\n[GABARIT DE LA CATÉGORIE]',
        template_skeleton,
        '\n[FICHES EXISTANTES DE CETTE CATÉGORIE (ne pas dupliquer un id, relier via related)]',
        existing or '(aucune)',
        "\n[DEMANDE DE L'AUTEUR]",
        brief,
        '\n[CONSIGNE]',
        (
            'Propose une nouvelle fiche markdown au même format que le gabarit '
            'ci-dessus (frontmatter YAML + corps), cohérente avec le manifeste de '
            'style et les fiches existantes. Retourne uniquement le contenu de la '
            "fiche (frontmatter + corps), rien d'autre."
        ),
    ]
    return '\n'.join(sections)


def compose_section_context(
    manifest_text: str,
    item: EtherItem,
    heading: str,
    brief: str,
) -> str:
    """Build the prompt asking the backend to draft a single fiche section."""
    sections = [
        '[MANIFESTE DE STYLE]',
        manifest_text or _NO_MANIFEST,
        f'\n[FICHE CIBLE] {item.name} ({item.type})',
        f'\n[SECTION À RÉDIGER] ## {heading}',
        "\n[DEMANDE DE L'AUTEUR]",
        brief,
        '\n[CONSIGNE]',
        (
            f'Rédige uniquement le contenu markdown de la section "## {heading}" '
            'décrite ci-dessus (sans répéter le titre de section), cohérent avec '
            'le manifeste de style. Ne retourne que ce contenu.'
        ),
    ]
    return '\n'.join(sections)
