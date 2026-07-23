"""Tests for `ether.web.routers.stories`: browse/create/edit sagas -> tomes -> acts -> chapters."""

from __future__ import annotations

from typing import TYPE_CHECKING

if TYPE_CHECKING:  # pragma: no cover
    from fastapi.testclient import TestClient


class TestStoriesIndex:
    def test_lists_sagas_and_one_shots(self, client: TestClient) -> None:
        response = client.get('/stories')

        assert response.status_code == 200
        assert 'saga-test' in response.text
        assert 'one-shot-test' in response.text


class TestCreateSaga:
    def test_create_saga_scaffolds_manifest_only(self, client: TestClient) -> None:
        response = client.post(
            '/stories',
            data={'slug': 'nouvelle-saga', 'nom': 'Nouvelle Saga', 'kind': 'saga'},
            follow_redirects=False,
        )

        assert response.status_code == 303
        assert response.headers['location'] == '/stories/nouvelle-saga'

        from ether.config import get_settings

        settings = get_settings()
        assert (settings.stories_path / 'nouvelle-saga' / '_manifest.md').is_file()
        assert not (settings.stories_path / 'nouvelle-saga' / '_index.md').exists()

    def test_create_one_shot_scaffolds_manifest_and_index(self, client: TestClient) -> None:
        client.post(
            '/stories',
            data={'slug': 'nouveau-one-shot', 'nom': 'Nouveau', 'kind': 'one-shot'},
            follow_redirects=False,
        )

        from ether.config import get_settings

        settings = get_settings()
        assert (settings.stories_path / 'nouveau-one-shot' / '_manifest.md').is_file()
        assert (settings.stories_path / 'nouveau-one-shot' / '_index.md').is_file()

    def test_duplicate_slug_conflicts(self, client: TestClient) -> None:
        response = client.post('/stories', data={'slug': 'saga-test', 'nom': 'x', 'kind': 'saga'})

        assert response.status_code == 409


class TestSagaTomeActChapterChain:
    def test_saga_detail_lists_tomes(self, client: TestClient) -> None:
        response = client.get('/stories/saga-test')

        assert response.status_code == 200
        assert 'Tome 1' in response.text

    def test_create_tome_then_act_then_chapter(self, client: TestClient) -> None:
        from ether.config import get_settings

        settings = get_settings()

        resp = client.post(
            '/stories/saga-test/tomes',
            data={
                'slug': 'tome-2',
                'numero': '2',
                'titre': 'Tome 2',
                'theme_specifique': 'x',
                'question_centrale': 'y',
            },
            follow_redirects=False,
        )
        assert resp.status_code == 303
        assert (settings.stories_path / 'saga-test' / 'tome-2' / '_index.md').is_file()

        resp = client.post(
            '/stories/tomes/tome-2/actes',
            data={'slug': 'act-2', 'numero': '1', 'titre': 'Acte 1', 'fonction_narrative': 'setup'},
            follow_redirects=False,
        )
        assert resp.status_code == 303
        act_dir = settings.stories_path / 'saga-test' / 'tome-2' / 'act-2'
        assert (act_dir / '_index.md').is_file()
        assert (act_dir / '_chapter').is_dir()

        resp = client.post(
            '/stories/actes/act-2/chapters',
            data={
                'slug': 'chap-1',
                'numero': '1',
                'titre': 'Le début',
                'etat_initial_protagoniste': 'a',
                'etat_final_protagoniste': 'b',
                'related': 'hero, citadel',
            },
            follow_redirects=False,
        )
        assert resp.status_code == 303
        assert resp.headers['location'] == '/stories/chapters/chap-1'

        from ether.stories.frontmatter import parse_file

        chapter_path = act_dir / '_chapter' / 'chap-1.md'
        assert chapter_path.is_file()
        chapter_meta, _ = parse_file(chapter_path)
        assert chapter_meta.related == ['hero', 'citadel']

        assert client.get('/stories/tomes/tome-2').status_code == 200
        assert client.get('/stories/actes/act-2').status_code == 200
        assert client.get('/stories/chapters/chap-1').status_code == 200


class TestOneShotActChain:
    def test_create_act_directly_under_one_shot(self, client: TestClient) -> None:
        from ether.config import get_settings

        settings = get_settings()

        resp = client.post(
            '/stories/one-shot-test/actes',
            data={'slug': 'act-2', 'numero': '2', 'titre': 'Acte 2'},
            follow_redirects=False,
        )

        assert resp.status_code == 303
        assert (settings.stories_path / 'one-shot-test' / 'act-2' / '_index.md').is_file()

    def test_cannot_create_tome_under_one_shot(self, client: TestClient) -> None:
        resp = client.post(
            '/stories/one-shot-test/tomes',
            data={'slug': 'x', 'numero': '1', 'titre': 'x'},
        )

        assert resp.status_code == 400

    def test_cannot_create_act_directly_under_saga_with_tomes(self, client: TestClient) -> None:
        resp = client.post(
            '/stories/saga-test/actes',
            data={'slug': 'x', 'numero': '1', 'titre': 'x'},
        )

        assert resp.status_code == 400


class TestArcs:
    def test_saga_page_links_to_arcs_with_count(self, client: TestClient) -> None:
        response = client.get('/stories/saga-test')

        assert response.status_code == 200
        assert 'Arcs (1)' in response.text

    def test_arcs_index_lists_existing_arc(self, client: TestClient) -> None:
        response = client.get('/stories/saga-test/arcs')

        assert response.status_code == 200
        assert 'Arc de Hero' in response.text
        assert 'tome-1' in response.text

    def test_create_arc_scoped_to_a_tome(self, client: TestClient) -> None:
        from ether.config import get_settings
        from ether.stories.frontmatter import parse_file

        settings = get_settings()

        resp = client.post(
            '/stories/saga-test/arcs',
            data={
                'slug': 'arc-2',
                'titre': 'Nouvel arc',
                'type_fiche': 'arc-intrigue',
                'scope': 'tome-1-act-1',
                'related': 'hero, sidekick',
            },
            follow_redirects=False,
        )

        assert resp.status_code == 303
        assert resp.headers['location'] == '/stories/arcs/arc-2'

        arc_path = settings.stories_path / 'saga-test' / 'arcs' / 'arc-2.md'
        assert arc_path.is_file()
        meta, _ = parse_file(arc_path)
        assert meta.type == 'arc-intrigue'
        assert meta.scope == 'tome-1-act-1'
        assert meta.related == ['hero', 'sidekick']

        assert client.get('/stories/arcs/arc-2').status_code == 200

    def test_duplicate_arc_slug_conflicts(self, client: TestClient) -> None:
        response = client.post(
            '/stories/saga-test/arcs',
            data={'slug': 'arc-1', 'titre': 'x'},
        )

        assert response.status_code == 409

    def test_edit_arc(self, client: TestClient) -> None:
        resp = client.post(
            '/stories/arcs/arc-1/edit',
            data={
                'titre': 'Arc de Hero (revu)',
                'type_fiche': 'arc-personnage',
                'statut': 'en cours',
                'scope': 'tome-1-act-1',
                'related': 'hero',
                'body': 'Nouveau corps.',
            },
            follow_redirects=False,
        )

        assert resp.status_code == 303

        detail = client.get('/stories/arcs/arc-1')
        assert 'Arc de Hero (revu)' in detail.text
        assert 'Nouveau corps' in detail.text

    def test_unknown_arc_is_404(self, client: TestClient) -> None:
        assert client.get('/stories/arcs/nonexistent').status_code == 404

    def test_unknown_saga_arcs_index_is_404(self, client: TestClient) -> None:
        assert client.get('/stories/nonexistent/arcs').status_code == 404


class TestChapterEdit:
    def test_edit_form_and_submit(self, client: TestClient) -> None:
        chapter_id = 'saga-test-tome-1-act-1-chapitre-1'

        assert client.get(f'/stories/chapters/{chapter_id}/edit').status_code == 200

        resp = client.post(
            f'/stories/chapters/{chapter_id}/edit',
            data={
                'titre': 'Chapitre 1 (revu)',
                'numero': '1',
                'statut': 'validé',
                'body': 'Nouveau corps.',
                'etat_initial_protagoniste': 'x',
                'etat_final_protagoniste': 'y',
                'related': 'hero',
            },
            follow_redirects=False,
        )
        assert resp.status_code == 303

        detail = client.get(f'/stories/chapters/{chapter_id}')
        assert 'Chapitre 1 (revu)' in detail.text
        assert 'Nouveau corps' in detail.text

    def test_unknown_chapter_is_404(self, client: TestClient) -> None:
        assert client.get('/stories/chapters/nonexistent').status_code == 404


class TestSagaTomeActeEdit:
    def test_edit_one_shot(self, client: TestClient) -> None:
        assert client.get('/stories/one-shot-test/edit').status_code == 200

        resp = client.post(
            '/stories/one-shot-test/edit',
            data={'nom': 'One Shot Test (revu)', 'statut': 'en cours', 'related': 'hero'},
            follow_redirects=False,
        )
        assert resp.status_code == 303

        detail = client.get('/stories/one-shot-test')
        assert 'One Shot Test (revu)' in detail.text

    def test_edit_a_saga_scaffolds_its_own_index_on_first_save(self, client: TestClient) -> None:
        """A saga (unlike a one-shot) has no _index.md until the first edit creates one."""
        from ether.config import get_settings

        settings = get_settings()
        index_path = settings.stories_path / 'saga-test' / '_index.md'
        assert not index_path.exists()

        assert client.get('/stories/saga-test/edit').status_code == 200

        resp = client.post(
            '/stories/saga-test/edit',
            data={'nom': 'Saga Test (revu)', 'statut': 'en cours', 'related': 'hero'},
            follow_redirects=False,
        )
        assert resp.status_code == 303
        assert index_path.is_file()

        detail = client.get('/stories/saga-test')
        assert 'Saga Test (revu)' in detail.text

    def test_editing_the_saga_again_updates_the_existing_index(self, client: TestClient) -> None:
        client.post(
            '/stories/saga-test/edit',
            data={'nom': 'First', 'statut': 'brouillon', 'related': ''},
        )
        client.post(
            '/stories/saga-test/edit',
            data={'nom': 'Second', 'statut': 'en cours', 'related': ''},
        )

        detail = client.get('/stories/saga-test')
        assert 'Second' in detail.text
        assert 'First' not in detail.text

    def test_edit_tome(self, client: TestClient) -> None:
        tome_id = 'saga-test-tome-1'
        assert client.get(f'/stories/tomes/{tome_id}/edit').status_code == 200

        resp = client.post(
            f'/stories/tomes/{tome_id}/edit',
            data={
                'titre': 'Tome 1 (revu)',
                'numero': '1',
                'statut': 'en cours',
                'theme_specifique': 'nouveau theme',
                'question_centrale': 'nouvelle question',
                'related': 'hero',
            },
            follow_redirects=False,
        )
        assert resp.status_code == 303

        detail = client.get(f'/stories/tomes/{tome_id}')
        assert 'Tome 1 (revu)' in detail.text
        assert 'nouveau theme' in detail.text

    def test_edit_acte(self, client: TestClient) -> None:
        act_id = 'saga-test-tome-1-act-1'
        assert client.get(f'/stories/actes/{act_id}/edit').status_code == 200

        resp = client.post(
            f'/stories/actes/{act_id}/edit',
            data={
                'titre': 'Acte 1 (revu)',
                'numero': '1',
                'statut': 'en cours',
                'fonction_narrative': 'nouvelle fonction',
                'related': 'hero',
            },
            follow_redirects=False,
        )
        assert resp.status_code == 303

        detail = client.get(f'/stories/actes/{act_id}')
        assert 'Acte 1 (revu)' in detail.text
        assert 'nouvelle fonction' in detail.text
