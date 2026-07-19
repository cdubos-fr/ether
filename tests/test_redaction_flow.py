"""Tests for `ether.sequencer.redaction` and `ether.web.routers.redaction`."""

from __future__ import annotations

import html
import re
from typing import TYPE_CHECKING

if TYPE_CHECKING:  # pragma: no cover
    from fastapi.testclient import TestClient

_DRAFT_RE = re.compile(r'<textarea name="draft"[^>]*>(.*)</textarea>', re.DOTALL)


def _extract_draft(html_text: str) -> str:
    match = _DRAFT_RE.search(html_text)
    assert match is not None
    return html.unescape(match.group(1))


def _create_chapitre_and_partie(client: TestClient) -> int:
    client.post('/sequencer/tomes', data={'numero': '1', 'titre': 'Tome I'})
    client.post('/sequencer/tomes/1/actes', data={'numero': '1', 'titre': 'La Rupture'})
    client.post(
        '/sequencer/actes/1/chapitres',
        data={
            'numero': '1',
            'titre': 'Le Réveil',
            'objectif_narratif': 'Introduire Hero',
            'etat_initial_protagoniste': 'Ignorant',
            'etat_final_protagoniste': 'Éveillé',
        },
    )
    client.post('/sequencer/chapitres/1/fiches-liees', data={'fiches_liees': 'hero, citadel'})
    client.post(
        '/sequencer/chapitres/1/parties',
        data={'numero': '1', 'objectif': 'Hero se réveille'},
    )
    return 1


class TestComposeRedactionContext:
    def test_pulls_linked_fiches_and_manifest(self, indexed: None) -> None:
        from ether.config import get_settings
        from ether.db import get_session
        from ether.sequencer.models import Chapitre
        from ether.sequencer.redaction import compose_redaction_context

        with get_session() as session:
            # acte_id=1 need not exist here; only the linked fiches/manifest matter for this test.
            chapitre = Chapitre(
                numero=1,
                titre='Ch1',
                acte_id=1,
                fiches_liees_json='["hero", "citadel"]',
            )
            session.add(chapitre)
            session.commit()
            session.refresh(chapitre)
            assert chapitre.id is not None

            ctx = compose_redaction_context(
                session,
                get_settings(),
                chapitre_id=chapitre.id,
                partie_id=None,
                instruction='Écris la scène.',
                contraintes='',
            )

        assert {f.id for f in ctx.fiches_liees} == {'hero', 'citadel'}
        assert ctx.instruction == 'Écris la scène.'


class TestRedactionRoutes:
    def test_generate_then_validate_persists_prose(self, client: TestClient) -> None:
        partie_id = _create_chapitre_and_partie(client)

        generated = client.post(
            f'/redaction/{partie_id}/generer',
            data={
                'instruction': 'Hero se réveille, plein de peur.',
                'contraintes': 'Pas de dialogue.',
            },
        )
        assert generated.status_code == 200
        draft = _extract_draft(generated.text)

        validated = client.post(
            f'/redaction/{partie_id}/valider',
            data={'draft': draft},
            follow_redirects=False,
        )
        assert validated.status_code == 303

        chapitre_page = client.get('/sequencer/chapitres/1')
        assert 'Validé' in chapitre_page.text

    def test_unknown_partie_is_404(self, client: TestClient) -> None:
        assert client.get('/redaction/999').status_code == 404
