"""Tests for `ether.web.routers.tags`."""

from __future__ import annotations

from typing import TYPE_CHECKING

if TYPE_CHECKING:  # pragma: no cover
    from fastapi.testclient import TestClient


class TestTagsIndex:
    def test_lists_tags_with_counts(self, client: TestClient) -> None:
        response = client.get('/tags')

        assert response.status_code == 200
        assert 'index' in response.text
        assert 'protagoniste' in response.text


class TestTagDetail:
    def test_lists_items_carrying_the_tag(self, client: TestClient) -> None:
        response = client.get('/tags/index')

        assert response.status_code == 200
        assert 'Personnages' in response.text
        assert 'Lieux' in response.text

    def test_unknown_tag_is_404(self, client: TestClient) -> None:
        response = client.get('/tags/nonexistent')

        assert response.status_code == 404

    def test_tag_link_on_item_page_navigates_here(self, client: TestClient) -> None:
        item_page = client.get('/item/hero')
        assert 'href="/tags/protagoniste"' in item_page.text

        response = client.get('/tags/protagoniste')
        assert response.status_code == 200
        assert 'Hero' in response.text
