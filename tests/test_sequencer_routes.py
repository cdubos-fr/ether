"""Tests for `ether.web.routers.sequencer`."""

from __future__ import annotations

from typing import TYPE_CHECKING

if TYPE_CHECKING:  # pragma: no cover
    from fastapi.testclient import TestClient


def _create_full_chain(client: TestClient) -> dict[str, int]:
    client.post(
        '/sequencer/tomes',
        data={
            'numero': '1',
            'titre': 'Tome I',
            'theme_specifique': 'Éveil',
            'question_centrale': 'Qui ?',
        },
    )
    client.post(
        '/sequencer/tomes/1/actes',
        data={'numero': '1', 'titre': 'La Rupture', 'fonction_narrative': 'Incident déclencheur'},
    )
    client.post(
        '/sequencer/actes/1/chapitres',
        data={'numero': '1', 'titre': 'Le Réveil', 'objectif_narratif': 'Introduire Hero'},
    )
    client.post(
        '/sequencer/chapitres/1/parties',
        data={'numero': '1', 'objectif': 'Hero se réveille'},
    )
    return {'tome_id': 1, 'acte_id': 1, 'chapitre_id': 1, 'partie_id': 1}


class TestSequencerChain:
    def test_create_tome_acte_chapitre_partie(self, client: TestClient) -> None:
        ids = _create_full_chain(client)

        assert client.get('/sequencer').text.count('Tome I') >= 1
        assert 'La Rupture' in client.get(f'/sequencer/tomes/{ids["tome_id"]}').text
        assert 'Le Réveil' in client.get(f'/sequencer/actes/{ids["acte_id"]}').text
        assert 'Scène 1' in client.get(f'/sequencer/chapitres/{ids["chapitre_id"]}').text

    def test_unknown_tome_is_404(self, client: TestClient) -> None:
        assert client.get('/sequencer/tomes/999').status_code == 404

    def test_creating_acte_under_unknown_tome_is_404(self, client: TestClient) -> None:
        response = client.post('/sequencer/tomes/999/actes', data={'numero': '1', 'titre': 'X'})
        assert response.status_code == 404


class TestFichesLiees:
    def test_link_and_display_univers_fiches(self, client: TestClient) -> None:
        ids = _create_full_chain(client)

        response = client.post(
            f'/sequencer/chapitres/{ids["chapitre_id"]}/fiches-liees',
            data={'fiches_liees': 'hero, citadel'},
            follow_redirects=False,
        )
        assert response.status_code == 303

        page = client.get(f'/sequencer/chapitres/{ids["chapitre_id"]}')
        assert 'hero, citadel' in page.text
