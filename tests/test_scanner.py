"""Tests for `ether.univers.scanner`."""

from __future__ import annotations

from typing import TYPE_CHECKING

from ether.univers import scanner

if TYPE_CHECKING:  # pragma: no cover
    from pathlib import Path


class TestWalkRepo:
    def test_finds_content_fiches_and_index_files(self, univers_root: Path) -> None:
        result = scanner.walk_repo(univers_root)
        ids = {fiche.meta.id for fiche in result.fiches}

        assert ids == {'personnages-index', 'hero', 'sidekick', 'lieux-index', 'citadel'}
        assert result.issues == []

    def test_excludes_template_files(self, univers_root: Path) -> None:
        result = scanner.walk_repo(univers_root)

        assert all(fiche.path.stem != '_template' for fiche in result.fiches)

    def test_excludes_style_manifest(self, univers_root: Path) -> None:
        (univers_root / '_manifest.md').write_text(
            "---\nupdated: 2026-07-19\n---\n\n# Manifeste d'écriture — Test\n",
            encoding='utf-8',
        )

        result = scanner.walk_repo(univers_root)

        assert result.issues == []
        assert all(fiche.path.name != '_manifest.md' for fiche in result.fiches)

    def test_flags_index_files(self, univers_root: Path) -> None:
        result = scanner.walk_repo(univers_root)
        by_id = {fiche.meta.id: fiche for fiche in result.fiches}

        assert by_id['personnages-index'].is_index is True
        assert by_id['hero'].is_index is False

    def test_reports_malformed_files_as_issues(self, univers_root: Path) -> None:
        broken = univers_root / 'personnages' / 'broken.md'
        broken.write_text('no frontmatter here', encoding='utf-8')

        result = scanner.walk_repo(univers_root)

        assert len(result.issues) == 1
        assert result.issues[0].path.name == 'broken.md'


class TestCategoryHelpers:
    def test_list_categories(self, univers_root: Path) -> None:
        assert scanner.list_categories(univers_root) == ['lieux', 'personnages']

    def test_find_template_and_index(self, univers_root: Path) -> None:
        assert scanner.find_template(univers_root, 'personnages') is not None
        assert scanner.find_index(univers_root, 'personnages') is not None
        assert scanner.find_template(univers_root, 'nonexistent') is None

    def test_read_template_skeleton_extracts_fences(self, univers_root: Path) -> None:
        template_path = scanner.find_template(univers_root, 'personnages')
        assert template_path is not None

        skeleton = scanner.read_template_skeleton(template_path)

        assert 'id: {{slug-unique}}' in skeleton
        assert '## Description' in skeleton
        assert 'À copier pour tout nouveau personnage' not in skeleton
