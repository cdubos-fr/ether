"""Tome → Acte → Chapitre → Partie: the sequencer's operational state.

Ported from the prior `studio-conception-narrative` app's `main_models.py`,
trimmed of its Codex-specific fields — world-building lore now lives in the
univers markdown repo, not here. `ArcNarratif`/`ArcState` are likewise
dropped: arcs are just univers fiches now (`type: arc-*`), linked to a
chapter via `Chapitre.fiches_liees` instead of a parallel DB-only system.
"""

# `from __future__ import annotations` is deliberately omitted here (unlike every
# other module in this package): combined with Python 3.14's native deferred
# annotation evaluation (PEP 649), it breaks SQLAlchemy 2.0.51's forward-ref
# resolution for generic `Relationship` types (`list['Acte']` etc.) with a
# spurious `InvalidRequestError`. See `ether/sequencer/models.py`'s lint
# override in pyproject.toml.

from sqlmodel import Field
from sqlmodel import Relationship
from sqlmodel import SQLModel


class Tome(SQLModel, table=True):
    """A single book of the saga."""

    id: int | None = Field(default=None, primary_key=True)
    numero: int
    titre: str
    theme_specifique: str = ''
    question_centrale: str = ''

    actes: list[Acte] = Relationship(back_populates='tome')


class Acte(SQLModel, table=True):
    """A narrative act within a `Tome` (typically 1, 2, or 3)."""

    id: int | None = Field(default=None, primary_key=True)
    numero: int
    titre: str
    fonction_narrative: str = ''

    tome_id: int = Field(foreign_key='tome.id')
    tome: Tome = Relationship(back_populates='actes')

    chapitres: list[Chapitre] = Relationship(back_populates='acte')


class Chapitre(SQLModel, table=True):
    """A chapter's plan within an `Acte`."""

    id: int | None = Field(default=None, primary_key=True)
    numero: int
    titre: str
    objectif_narratif: str = ''
    etat_initial_protagoniste: str = ''
    etat_final_protagoniste: str = ''
    fiches_liees_json: str = Field(default='[]')

    acte_id: int = Field(foreign_key='acte.id')
    acte: Acte = Relationship(back_populates='chapitres')

    parties: list[Partie] = Relationship(back_populates='chapitre')


class Partie(SQLModel, table=True):
    """The smallest unit of redaction (a scene) within a `Chapitre`."""

    id: int | None = Field(default=None, primary_key=True)
    numero: int
    objectif: str = ''
    evenement_cle: str = ''
    impact_sur_protagoniste: str = ''
    statut: str = Field(default='À faire')
    contenu_genere: str | None = None

    chapitre_id: int = Field(foreign_key='chapitre.id')
    chapitre: Chapitre = Relationship(back_populates='parties')
