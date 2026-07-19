"""Tests for `ether.web.routers.fiche_edit`."""

from __future__ import annotations

from typing import TYPE_CHECKING

if TYPE_CHECKING:  # pragma: no cover
    from pathlib import Path

    from fastapi.testclient import TestClient


class TestWholeFileEdit:
    def test_edit_form_renders(self, client: TestClient) -> None:
        response = client.get('/item/hero/edit')

        assert response.status_code == 200
        assert 'Hero' in response.text

    def test_edit_writes_through_to_markdown(self, client: TestClient, univers_root: Path) -> None:
        response = client.post(
            '/item/hero/edit',
            data={
                'name': 'Hero',
                'status': 'theorise',
                'aliases': '',
                'tags': 'protagoniste, brave',
                'related': 'sidekick, citadel',
                'updated': '2026-07-19',
                'body': '# Hero\n\n## Description\n\nUpdated.\n',
            },
            follow_redirects=False,
        )

        assert response.status_code == 303
        assert response.headers['location'] == '/item/hero'

        content = (univers_root / 'personnages' / 'hero.md').read_text(encoding='utf-8')
        assert 'status: theorise' in content
        assert 'tags: [protagoniste, brave]' in content
        assert 'updated: 2026-07-19' in content
        assert 'Updated.' in content

    def test_edit_reindexes_the_item(self, client: TestClient) -> None:
        client.post(
            '/item/hero/edit',
            data={
                'name': 'Hero',
                'status': 'theorise',
                'body': '# Hero\n',
            },
        )

        response = client.get('/item/hero')

        assert 'theorise' in response.text


class TestSectionEdit:
    def test_replace_existing_section(self, client: TestClient, univers_root: Path) -> None:
        response = client.post(
            '/item/hero/section',
            data={'heading': 'Description', 'content': 'Nouvelle description.', 'mode': 'replace'},
            follow_redirects=False,
        )

        assert response.status_code == 303
        content = (univers_root / 'personnages' / 'hero.md').read_text(encoding='utf-8')
        assert 'Nouvelle description.' in content
        assert "Le protagoniste de l'histoire." not in content

    def test_append_to_existing_section(self, client: TestClient, univers_root: Path) -> None:
        client.post(
            '/item/hero/section',
            data={
                'heading': 'Voir aussi',
                'content': '- [Citadel](../lieux/citadel.md)',
                'mode': 'append',
            },
        )

        content = (univers_root / 'personnages' / 'hero.md').read_text(encoding='utf-8')
        assert '[Sidekick](sidekick.md)' in content
        assert '[Citadel](../lieux/citadel.md)' in content

    def test_create_new_section(self, client: TestClient, univers_root: Path) -> None:
        response = client.post(
            '/item/sidekick/section',
            data={'heading': 'Voir aussi', 'content': '- [Hero](hero.md)', 'mode': 'replace'},
            follow_redirects=False,
        )

        assert response.status_code == 303
        content = (univers_root / 'personnages' / 'sidekick.md').read_text(encoding='utf-8')
        assert '## Voir aussi' in content
        assert '[Hero](hero.md)' in content
