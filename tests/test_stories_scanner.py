"""Tests for `ether.stories.scanner`."""

from __future__ import annotations

from typing import TYPE_CHECKING

from ether.stories import scanner

if TYPE_CHECKING:  # pragma: no cover
    from pathlib import Path


class TestWalkRepo:
    def test_finds_every_node_across_saga_and_one_shot(self, stories_root: Path) -> None:
        result = scanner.walk_repo(stories_root)
        ids = {node.meta.id for node in result.nodes}

        assert ids == {
            'stories-index',
            'saga-test-tome-1',
            'saga-test-tome-1-act-1',
            'saga-test-tome-1-act-1-chapitre-1',
            'one-shot-test-index',
            'one-shot-test-act-1',
            'one-shot-test-act-1-chapitre-1',
        }
        assert result.issues == []

    def test_saga_chapter_has_saga_and_tome(self, stories_root: Path) -> None:
        result = scanner.walk_repo(stories_root)
        by_id = {node.meta.id: node for node in result.nodes}

        chapter = by_id['saga-test-tome-1-act-1-chapitre-1']
        assert chapter.saga == 'saga-test'
        assert chapter.tome == 'tome-1'
        assert chapter.is_index is False

    def test_one_shot_chapter_has_no_tome(self, stories_root: Path) -> None:
        result = scanner.walk_repo(stories_root)
        by_id = {node.meta.id: node for node in result.nodes}

        chapter = by_id['one-shot-test-act-1-chapitre-1']
        assert chapter.saga == 'one-shot-test'
        assert chapter.tome == ''

    def test_flags_index_nodes(self, stories_root: Path) -> None:
        result = scanner.walk_repo(stories_root)
        by_id = {node.meta.id: node for node in result.nodes}

        assert by_id['saga-test-tome-1'].is_index is True
        assert by_id['saga-test-tome-1-act-1-chapitre-1'].is_index is False

    def test_reports_malformed_chapter_as_issue(self, stories_root: Path) -> None:
        broken = stories_root / 'saga-test' / 'tome-1' / 'act-1' / '_chapter' / 'broken.md'
        broken.write_text('no frontmatter here', encoding='utf-8')

        result = scanner.walk_repo(stories_root)

        assert len(result.issues) == 1
        assert result.issues[0].path.name == 'broken.md'

    def test_missing_root_yields_empty_result(self, tmp_path: Path) -> None:
        result = scanner.walk_repo(tmp_path / 'does-not-exist')

        assert result.nodes == []
        assert result.issues == []
