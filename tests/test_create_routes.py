"""Tests for `ether.web.routers.create` (AI-assisted creation panel)."""

from __future__ import annotations

import html
import re
from typing import TYPE_CHECKING

if TYPE_CHECKING:  # pragma: no cover
    from pathlib import Path

    from fastapi.testclient import TestClient

_DRAFT_RE = re.compile(r'<textarea name="draft"[^>]*>(.*)</textarea>', re.DOTALL)


def _extract_draft(html_text: str) -> str:
    match = _DRAFT_RE.search(html_text)
    assert match is not None, 'no draft textarea found in response'
    return html.unescape(match.group(1))


class TestCreateIndex:
    def test_lists_categories_and_items(self, client: TestClient) -> None:
        response = client.get('/create')

        assert response.status_code == 200
        assert 'personnages' in response.text
        assert 'Hero' in response.text

    def test_unknown_category_form_is_404(self, client: TestClient) -> None:
        response = client.get('/create/nonexistent')

        assert response.status_code == 404


class TestCreateNewFiche:
    def test_generate_then_save_writes_a_new_file(
        self,
        client: TestClient,
        univers_root: Path,
    ) -> None:
        generated = client.post('/create/personnages/generate', data={'brief': 'A jealous rival.'})
        assert generated.status_code == 200
        draft = _extract_draft(generated.text)

        saved = client.post(
            '/create/personnages/save',
            data={'draft': draft},
            follow_redirects=False,
        )

        assert saved.status_code == 303
        new_id = saved.headers['location'].rsplit('/', 1)[-1]
        new_path = univers_root / 'personnages' / f'{new_id}.md'
        assert new_path.is_file()
        assert new_id.startswith('stub-')

    def test_saved_item_is_immediately_browsable(self, client: TestClient) -> None:
        generated = client.post('/create/personnages/generate', data={'brief': 'A jealous rival.'})
        draft = _extract_draft(generated.text)
        saved = client.post(
            '/create/personnages/save',
            data={'draft': draft},
            follow_redirects=False,
        )
        new_id = saved.headers['location'].rsplit('/', 1)[-1]

        response = client.get(f'/item/{new_id}')

        assert response.status_code == 200

    def test_save_rejects_unparseable_draft(self, client: TestClient) -> None:
        response = client.post('/create/personnages/save', data={'draft': 'not frontmatter at all'})

        assert response.status_code == 400

    def test_save_rejects_duplicate_id(self, client: TestClient) -> None:
        draft = (
            '---\nid: hero\ntype: personnage\nname: "Duplicate"\naliases: []\n'
            'status: brouillon\ntags: []\nrelated: []\nupdated: 2026-07-19\n---\n\n# Duplicate\n'
        )

        response = client.post('/create/personnages/save', data={'draft': draft})

        assert response.status_code == 409


class TestCreateSection:
    def test_form_renders_for_existing_item(self, client: TestClient) -> None:
        response = client.get('/item/hero/create-section')

        assert response.status_code == 200
        assert 'Hero' in response.text

    def test_unknown_item_is_404(self, client: TestClient) -> None:
        response = client.get('/item/nonexistent/create-section')

        assert response.status_code == 404

    def test_generate_then_save_patches_the_fiche(
        self,
        client: TestClient,
        univers_root: Path,
    ) -> None:
        generated = client.post(
            '/item/hero/create-section/generate',
            data={'heading': 'Objectifs', 'brief': 'His short-term goals.'},
        )
        draft = _extract_draft(generated.text)

        saved = client.post(
            '/item/hero/create-section/save',
            data={'heading': 'Objectifs', 'draft': draft, 'mode': 'replace'},
            follow_redirects=False,
        )

        assert saved.status_code == 303
        content = (univers_root / 'personnages' / 'hero.md').read_text(encoding='utf-8')
        assert '## Objectifs' in content
