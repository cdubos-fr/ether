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
