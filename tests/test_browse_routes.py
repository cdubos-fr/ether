"""Tests for `ether.web.routers.browse`."""

from __future__ import annotations

from typing import TYPE_CHECKING

if TYPE_CHECKING:  # pragma: no cover
    from fastapi.testclient import TestClient


class TestIndex:
    def test_lists_categories_with_counts(self, client: TestClient) -> None:
        response = client.get('/')

        assert response.status_code == 200
        assert 'personnages' in response.text
        assert 'lieux' in response.text


class TestBrowseCategory:
    def test_lists_items_in_category(self, client: TestClient) -> None:
        response = client.get('/browse/personnages')

        assert response.status_code == 200
        assert 'Hero' in response.text
        assert 'Sidekick' in response.text

    def test_unknown_category_is_404(self, client: TestClient) -> None:
        response = client.get('/browse/nonexistent')

        assert response.status_code == 404


class TestItemDetail:
    def test_shows_related_and_backlinks(self, client: TestClient) -> None:
        response = client.get('/item/hero')

        assert response.status_code == 200
        assert 'Sidekick' in response.text
        assert 'Citadel' in response.text  # outgoing related
        assert 'Référencé par' in response.text
        assert 'Personnages' in response.text  # backlink from personnages-index

    def test_dangling_link_is_flagged(self, client: TestClient) -> None:
        response = client.get('/item/citadel')

        assert response.status_code == 200
        assert 'dangling' in response.text
        assert 'lieu-fantome' in response.text

    def test_unknown_item_is_404(self, client: TestClient) -> None:
        response = client.get('/item/nonexistent')

        assert response.status_code == 404

    def test_index_backed_item_renders(self, client: TestClient) -> None:
        """`_index.md`-backed items (e.g. a category hub) are real, browsable fiches."""
        response = client.get('/item/lieux-index')

        assert response.status_code == 200
        assert 'Lieux' in response.text

    def test_prose_relative_md_link_is_rewritten_to_item_route(self, client: TestClient) -> None:
        """hero.md's body has `[Sidekick](sidekick.md)` — should render as `/item/sidekick`."""
        response = client.get('/item/hero')

        assert response.status_code == 200
        assert 'href="/item/sidekick"' in response.text
        assert 'sidekick.md' not in response.text
