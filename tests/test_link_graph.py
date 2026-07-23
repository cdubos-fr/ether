"""Tests for `ether.link_graph`: cross-domain `related:` resolution.

The fixture project's `arc-1.md` (`stories/saga-test/arcs/arc-1.md`) already
has `related: [hero]` — a real stories -> univers cross-domain link, used
throughout without needing to touch either fixture's other, count-sensitive
`related:` fields (see `tests/test_indexer_links.py`'s exact link counts).
"""

from __future__ import annotations

from pathlib import Path
from typing import TYPE_CHECKING

from ether import link_graph
from ether.stories.indexer import reindex as reindex_stories
from ether.univers.indexer import reindex as reindex_univers

if TYPE_CHECKING:  # pragma: no cover
    from sqlmodel import Session

_HERO_PATH = Path('univers/personnages/hero.md')


def _reindex_both(univers_root: Path, stories_root: Path, session: Session) -> None:
    reindex_univers(univers_root, session)
    reindex_stories(stories_root, session)


class TestKnownIds:
    def test_spans_both_domains(
        self,
        ether_env: None,
        univers_root: Path,
        stories_root: Path,
    ) -> None:
        from ether.db import get_session

        with get_session() as session:
            _reindex_both(univers_root, stories_root, session)
            ids = link_graph.known_ids(session)

        assert 'hero' in ids
        assert 'arc-1' in ids
        assert 'saga-test-tome-1-act-1-chapitre-1' in ids


class TestResolveAndUrl:
    def test_resolves_a_univers_item(
        self,
        ether_env: None,
        univers_root: Path,
        stories_root: Path,
    ) -> None:
        from ether.db import get_session

        with get_session() as session:
            _reindex_both(univers_root, stories_root, session)
            item = link_graph.resolve_item(session, 'hero')
            assert item is not None
            assert link_graph.item_url(item) == '/item/hero'

    def test_resolves_each_story_node_type(
        self,
        ether_env: None,
        univers_root: Path,
        stories_root: Path,
    ) -> None:
        from ether.db import get_session

        with get_session() as session:
            _reindex_both(univers_root, stories_root, session)

            tome = link_graph.resolve_item(session, 'saga-test-tome-1')
            act = link_graph.resolve_item(session, 'saga-test-tome-1-act-1')
            chapter = link_graph.resolve_item(session, 'saga-test-tome-1-act-1-chapitre-1')
            arc = link_graph.resolve_item(session, 'arc-1')
            one_shot = link_graph.resolve_item(session, 'one-shot-test-index')

            assert tome is not None
            assert act is not None
            assert chapter is not None
            assert arc is not None
            assert one_shot is not None

            assert link_graph.item_url(tome) == '/stories/tomes/saga-test-tome-1'
            assert link_graph.item_url(act) == '/stories/actes/saga-test-tome-1-act-1'
            expected_chapter_url = '/stories/chapters/saga-test-tome-1-act-1-chapitre-1'
            assert link_graph.item_url(chapter) == expected_chapter_url
            assert link_graph.item_url(arc) == '/stories/arcs/arc-1'
            assert link_graph.item_url(one_shot) == '/stories/one-shot-test'

    def test_resolves_none_for_unknown_id(
        self,
        ether_env: None,
        univers_root: Path,
        stories_root: Path,
    ) -> None:
        from ether.db import get_session

        with get_session() as session:
            _reindex_both(univers_root, stories_root, session)
            assert link_graph.resolve_item(session, 'nonexistent') is None


class TestCrossDomainViews:
    def test_arc_outgoing_resolves_to_a_univers_character(
        self,
        ether_env: None,
        univers_root: Path,
        stories_root: Path,
    ) -> None:
        from ether.db import get_session

        with get_session() as session:
            _reindex_both(univers_root, stories_root, session)
            views = link_graph.outgoing_views(session, 'arc-1')

        assert views == [{'id': 'hero', 'name': 'Hero', 'url': '/item/hero'}]

    def test_character_backlinks_include_the_arc(
        self,
        ether_env: None,
        univers_root: Path,
        stories_root: Path,
    ) -> None:
        from ether.db import get_session

        with get_session() as session:
            _reindex_both(univers_root, stories_root, session)
            views = link_graph.backlink_views(session, 'hero')

        by_id = {v['id']: v for v in views}
        assert 'arc-1' in by_id
        assert by_id['arc-1']['url'] == '/stories/arcs/arc-1'
        assert by_id['arc-1']['name'] == 'Arc de Hero'


class TestDanglingAcrossDomains:
    def test_link_is_dangling_only_until_the_other_domain_indexes(
        self,
        ether_env: None,
        univers_root: Path,
        stories_root: Path,
    ) -> None:
        from ether.db import get_session

        with get_session() as session:
            reindex_stories(stories_root, session)  # univers not indexed yet
            [arc_link] = link_graph.outgoing_views(session, 'arc-1')
            assert arc_link['url'] is None

            reindex_univers(univers_root, session)  # hero now exists too
            [arc_link] = link_graph.outgoing_views(session, 'arc-1')
            assert arc_link['url'] == '/item/hero'


class TestOrphanCleanup:
    def test_removing_a_node_clears_its_stale_links_on_reindex(
        self,
        ether_env: None,
        univers_root: Path,
        stories_root: Path,
    ) -> None:
        from sqlmodel import select

        from ether.db import get_session

        with get_session() as session:
            _reindex_both(univers_root, stories_root, session)

        (stories_root / 'saga-test' / 'arcs' / 'arc-1.md').unlink()

        with get_session() as session:
            reindex_stories(stories_root, session)
            remaining = session.exec(
                select(link_graph.EtherLink).where(link_graph.EtherLink.source_id == 'arc-1'),
            ).all()

        assert remaining == []


class TestUrlIndex:
    def test_covers_both_domains(
        self,
        ether_env: None,
        univers_root: Path,
        stories_root: Path,
    ) -> None:
        from ether.db import get_session

        with get_session() as session:
            _reindex_both(univers_root, stories_root, session)
            index = link_graph.url_index(session)

        assert index['univers/personnages/hero.md'] == '/item/hero'
        assert index['stories/saga-test/arcs/arc-1.md'] == '/stories/arcs/arc-1'


class TestRewriteRelativeLinks:
    def test_rewrites_same_directory_link(self) -> None:
        body = '- [Sidekick](sidekick.md)'
        paths = {'univers/personnages/sidekick.md': '/item/sidekick'}

        rewritten = link_graph.rewrite_relative_links(body, _HERO_PATH, paths)

        assert rewritten == '- [Sidekick](/item/sidekick)'

    def test_rewrites_cross_directory_link(self) -> None:
        body = 'Voir [Citadel](../lieux/citadel.md) pour plus de détails.'
        paths = {'univers/lieux/citadel.md': '/item/citadel'}

        rewritten = link_graph.rewrite_relative_links(body, _HERO_PATH, paths)

        assert rewritten == 'Voir [Citadel](/item/citadel) pour plus de détails.'

    def test_rewrites_link_from_stories_into_univers(self) -> None:
        body = 'Voir [Hero](../../../univers/personnages/hero.md).'
        paths = {'univers/personnages/hero.md': '/item/hero'}

        rewritten = link_graph.rewrite_relative_links(
            body,
            Path('stories/saga-test/arcs/arc-1.md'),
            paths,
        )

        assert rewritten == 'Voir [Hero](/item/hero).'

    def test_preserves_fragment(self) -> None:
        body = '[Gouvernance](../organisations/le-concile/_index.md#gouvernance)'
        paths = {'univers/organisations/le-concile/_index.md': '/item/le-concile'}

        rewritten = link_graph.rewrite_relative_links(body, _HERO_PATH, paths)

        assert rewritten == '[Gouvernance](/item/le-concile#gouvernance)'

    def test_leaves_unresolvable_links_untouched(self) -> None:
        body = '[Nowhere](../nowhere/ghost.md)'

        rewritten = link_graph.rewrite_relative_links(body, _HERO_PATH, {})

        assert rewritten == body

    def test_leaves_non_markdown_links_untouched(self) -> None:
        body = '[External](https://example.com) and [image](pic.png)'

        rewritten = link_graph.rewrite_relative_links(body, _HERO_PATH, {})

        assert rewritten == body

    def test_leaves_images_untouched(self) -> None:
        body = '![diagram](../assets/diagram.md)'
        paths = {'univers/assets/diagram.md': '/item/diagram'}

        rewritten = link_graph.rewrite_relative_links(body, _HERO_PATH, paths)

        assert rewritten == body
