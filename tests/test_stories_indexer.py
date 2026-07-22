"""Tests for `ether.stories.indexer`: index rebuild for the stories tree."""

from __future__ import annotations

from typing import TYPE_CHECKING

from ether.markdown_io import load_raw
from ether.markdown_io import write_file
from ether.stories.index_models import EtherStoryItem
from ether.stories.indexer import reindex
from ether.stories.indexer import reindex_one

if TYPE_CHECKING:  # pragma: no cover
    from pathlib import Path


class TestReindex:
    def test_counts_nodes(self, ether_env: None, stories_root: Path) -> None:
        from ether.db import get_session

        with get_session() as session:
            stats = reindex(stories_root, session)

        assert stats.items == 7
        assert stats.parse_errors == []

    def test_is_disposable_and_rebuildable(self, ether_env: None, stories_root: Path) -> None:
        """Deleting the index and rebuilding it must reproduce the same rows."""
        from ether.db import get_session

        with get_session() as session:
            first = reindex(stories_root, session)
            second = reindex(stories_root, session)

        assert first == second

    def test_chapter_row_carries_planning_fields(
        self,
        stories_indexed: None,
        stories_root: Path,
    ) -> None:
        from ether.db import get_session

        with get_session() as session:
            item = session.get(EtherStoryItem, 'saga-test-tome-1-act-1-chapitre-1')

        assert item is not None
        assert item.saga == 'saga-test'
        assert item.tome == 'tome-1'
        assert item.numero == 1
        assert item.etat_initial_protagoniste == 'Ignorant'
        assert item.etat_final_protagoniste == 'Éveillé'


class TestReindexOne:
    def test_refreshes_a_single_node_after_edit(
        self,
        stories_indexed: None,
        stories_root: Path,
    ) -> None:
        from ether.db import get_session

        path = stories_root / 'saga-test' / 'tome-1' / 'act-1' / '_chapter' / 'chapitre-1.md'
        raw, body = load_raw(path)
        raw['name'] = 'Chapitre 1 (revu)'
        write_file(path, raw, body)

        with get_session() as session:
            item = reindex_one(
                stories_root,
                'saga-test/tome-1/act-1/_chapter/chapitre-1.md',
                'saga-test',
                'tome-1',
                session,
            )
            item_name = item.name

        assert item_name == 'Chapitre 1 (revu)'
