"""Tests for `ether.univers.indexer`: index rebuild + link graph resolution."""

from __future__ import annotations

from typing import TYPE_CHECKING

from ether.univers.frontmatter import load_raw
from ether.univers.frontmatter import write_file
from ether.univers.index_models import EtherItem
from ether.univers.indexer import backlinks
from ether.univers.indexer import items_with_tag
from ether.univers.indexer import list_tags
from ether.univers.indexer import outgoing_links
from ether.univers.indexer import path_index
from ether.univers.indexer import reindex
from ether.univers.indexer import reindex_one

if TYPE_CHECKING:  # pragma: no cover
    from pathlib import Path


class TestReindex:
    def test_counts_items_and_links(self, ether_env: None, univers_root: Path) -> None:
        from ether.db import get_session

        with get_session() as session:
            stats = reindex(univers_root, session)

        assert stats.items == 5
        assert stats.links == 7
        assert stats.dangling_links == 1
        assert stats.parse_errors == []

    def test_is_disposable_and_rebuildable(self, ether_env: None, univers_root: Path) -> None:
        """Deleting the index and rebuilding it must reproduce the same rows."""
        from ether.db import get_session

        with get_session() as session:
            first = reindex(univers_root, session)
            second = reindex(univers_root, session)

        assert first == second


class TestLinkGraph:
    def test_outgoing_links_include_dangling(self, indexed: None, univers_root: Path) -> None:
        from ether.db import get_session

        with get_session() as session:
            links = outgoing_links(session, 'citadel')

        targets = {link.target_id: link.dangling for link in links}
        assert targets == {'hero': False, 'lieu-fantome': True}

    def test_backlinks_only_include_non_dangling_sources(self, indexed: None) -> None:
        from ether.db import get_session

        with get_session() as session:
            back = backlinks(session, 'hero')

        assert set(back) == {'sidekick', 'citadel', 'personnages-index'}


class TestReindexOne:
    def test_refreshes_a_single_item_after_edit(self, indexed: None, univers_root: Path) -> None:
        from ether.db import get_session

        path = univers_root / 'personnages' / 'hero.md'
        raw, body = load_raw(path)
        raw['related'] = ['sidekick']  # drop the citadel link
        write_file(path, raw, body)

        with get_session() as session:
            item = reindex_one(univers_root, 'personnages/hero.md', session)
            item_name = item.name
            remaining_links = outgoing_links(session, 'hero')

        assert item_name == 'Hero'
        assert {link.target_id for link in remaining_links} == {'sidekick'}

    def test_new_item_appears_after_reindex_one(self, indexed: None, univers_root: Path) -> None:
        from ether.db import get_session
        from ether.univers.frontmatter import new_frontmatter_mapping
        from ether.univers.schema import FicheFrontmatter

        meta = FicheFrontmatter(id='newcomer', type='personnage', name='Newcomer', related=['hero'])
        path = univers_root / 'personnages' / 'newcomer.md'
        write_file(path, new_frontmatter_mapping(meta), '# Newcomer\n')

        with get_session() as session:
            reindex_one(univers_root, 'personnages/newcomer.md', session)
            found = session.get(EtherItem, 'newcomer')
            assert found is not None
            assert found.category == 'personnages'

    def test_refreshes_tags_after_edit(self, indexed: None, univers_root: Path) -> None:
        from ether.db import get_session

        path = univers_root / 'personnages' / 'hero.md'
        raw, body = load_raw(path)
        raw['tags'] = ['protagoniste', 'brave']
        write_file(path, raw, body)

        with get_session() as session:
            reindex_one(univers_root, 'personnages/hero.md', session)
            tags = dict(list_tags(session))

        assert tags['brave'] == 1
        assert tags['protagoniste'] == 1


class TestTags:
    def test_list_tags_counts_across_fiches(self, indexed: None) -> None:
        from ether.db import get_session

        with get_session() as session:
            tags = dict(list_tags(session))

        assert tags == {'index': 2, 'protagoniste': 1}

    def test_items_with_tag(self, indexed: None) -> None:
        from ether.db import get_session

        with get_session() as session:
            items = items_with_tag(session, 'index')

        assert {item.id for item in items} == {'personnages-index', 'lieux-index'}

    def test_items_with_unknown_tag_is_empty(self, indexed: None) -> None:
        from ether.db import get_session

        with get_session() as session:
            items = items_with_tag(session, 'nonexistent')

        assert items == []


class TestPathIndex:
    def test_maps_relative_path_to_id(self, indexed: None) -> None:
        from ether.db import get_session

        with get_session() as session:
            paths = path_index(session)

        assert paths['personnages/hero.md'] == 'hero'
        assert paths['lieux/citadel.md'] == 'citadel'
