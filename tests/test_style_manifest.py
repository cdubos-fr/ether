"""Tests for `ether.ai.style_manifest` and `ether.web.routers.style`."""

from __future__ import annotations

from typing import TYPE_CHECKING

from ether.ai import style_manifest
from ether.ai.style_manifest import ManifestRule
from ether.ai.style_manifest import StyleManifestForm

if TYPE_CHECKING:  # pragma: no cover
    from pathlib import Path

    from fastapi.testclient import TestClient


class TestStyleManifestModule:
    def test_read_missing_manifest_returns_empty(self, tmp_path: Path) -> None:
        assert style_manifest.read_manifest(tmp_path / '_manifest.md') == ''

    def test_ensure_manifest_scaffolds_default_form(self, tmp_path: Path) -> None:
        path = tmp_path / '_manifest.md'

        style_manifest.ensure_manifest(path, 'My Universe')

        assert path.is_file()
        content = path.read_text(encoding='utf-8')
        assert 'My Universe' in content
        assert '## Intention thématique' in content
        assert '## Règles de prose' in content

    def test_ensure_manifest_does_not_overwrite_existing(self, tmp_path: Path) -> None:
        path = tmp_path / '_manifest.md'
        path.write_text('custom content', encoding='utf-8')

        style_manifest.ensure_manifest(path, 'My Universe')

        assert path.read_text(encoding='utf-8') == 'custom content'

    def test_write_manifest_overwrites(self, tmp_path: Path) -> None:
        path = tmp_path / '_manifest.md'
        style_manifest.write_manifest(path, 'first')
        style_manifest.write_manifest(path, 'second')

        assert style_manifest.read_manifest(path) == 'second'


class TestFormRoundTrip:
    def test_render_then_parse_round_trips_fields(self) -> None:
        form = StyleManifestForm(
            project_name='Saga Test',
            updated='2026-07-19',
            intention_thematique='Le courage face à la peur.',
            point_de_vue=[ManifestRule('Personne / temps', 'première personne, présent')],
            registre_ton='Sombre et sec.',
            regles_prose=[
                ManifestRule('Rythme', 'phrases courtes en tension'),
                ManifestRule('Dialogue', 'jamais de guillemets'),
            ],
            a_eviter='Les clichés de chevalier blanc.',
            format_sortie='markdown, tirets cadratins pour le dialogue.',
        )

        parsed = style_manifest.parse_markdown(
            style_manifest.render_markdown(form),
            fallback_project_name='unused',
        )

        assert parsed.project_name == 'Saga Test'
        assert parsed.updated == '2026-07-19'
        assert parsed.intention_thematique == 'Le courage face à la peur.'
        assert parsed.point_de_vue == [
            ManifestRule('Personne / temps', 'première personne, présent'),
        ]
        assert parsed.regles_prose == [
            ManifestRule('Rythme', 'phrases courtes en tension'),
            ManifestRule('Dialogue', 'jamais de guillemets'),
        ]
        assert parsed.a_eviter == 'Les clichés de chevalier blanc.'

    def test_parse_empty_text_falls_back_to_default_form(self) -> None:
        parsed = style_manifest.parse_markdown('', fallback_project_name='Fallback')

        assert parsed.project_name == 'Fallback'
        assert len(parsed.point_de_vue) == 3

    def test_parse_tolerates_unstructured_legacy_content(self) -> None:
        parsed = style_manifest.parse_markdown(
            'Some free-form text with no headings at all.',
            fallback_project_name='Fallback',
        )

        assert parsed.project_name == 'Fallback'
        assert parsed.intention_thematique == ''
        assert parsed.point_de_vue == []

    def test_render_omits_blank_rules(self) -> None:
        form = StyleManifestForm(
            project_name='X',
            regles_prose=[ManifestRule('', ''), ManifestRule('Rythme', 'court')],
        )

        rendered = style_manifest.render_markdown(form)

        assert '- **Rythme :** court' in rendered
        assert rendered.count('\n- ') <= 1


def _manifest_path(saga: str = 'one-shot-test') -> Path:
    from ether.config import get_settings

    return get_settings().manifest_path_for(saga)


class TestStyleIndex:
    def test_lists_sagas(self, client: TestClient) -> None:
        response = client.get('/style')

        assert response.status_code == 200
        assert 'one-shot-test' in response.text
        assert 'saga-test' in response.text


class TestStyleRoutes:
    def test_get_scaffolds_and_shows_manifest(self, client: TestClient) -> None:
        response = client.get('/style/one-shot-test')

        assert response.status_code == 200
        assert _manifest_path().is_file()
        assert 'Règles de prose' in response.text

    def test_post_persists_structured_edits(self, client: TestClient) -> None:
        client.get('/style/one-shot-test')  # scaffold first, like a real user would

        response = client.post(
            '/style/one-shot-test',
            data={
                'project_name': 'Saga Test',
                'intention_thematique': 'Le courage.',
                'registre_ton': 'Sombre et sec.',
                'a_eviter': 'Les clichés.',
                'format_sortie': 'markdown simple.',
                'pov_label': ['Personne / temps'],
                'pov_content': ['première personne'],
                'regle_label': ['Rythme', 'Dialogue'],
                'regle_content': ['phrases courtes', 'sans guillemets'],
            },
            follow_redirects=False,
        )

        assert response.status_code == 303
        content = _manifest_path().read_text(encoding='utf-8')
        assert 'Sombre et sec.' in content
        assert '- **Rythme :** phrases courtes' in content
        assert '- **Dialogue :** sans guillemets' in content

    def test_edited_manifest_is_reloaded_correctly_in_the_form(
        self,
        client: TestClient,
    ) -> None:
        client.get('/style/one-shot-test')
        client.post(
            '/style/one-shot-test',
            data={
                'project_name': 'Saga Test',
                'regle_label': ['Rythme'],
                'regle_content': ['phrases courtes'],
            },
        )

        response = client.get('/style/one-shot-test')

        assert 'Saga Test' in response.text
        assert 'phrases courtes' in response.text
