"""Tests for `ether.project.find_issues`."""

from __future__ import annotations

import shutil
from typing import TYPE_CHECKING

from ether.project import find_issues

if TYPE_CHECKING:  # pragma: no cover
    from pathlib import Path


class TestValidProject:
    def test_no_issues(self, project_root: Path) -> None:
        assert find_issues(project_root) == []


class TestEmptyIsValid:
    """Nothing is required to exist upfront: only what's there must be well-formed."""

    def test_brand_new_empty_root_is_valid(self, tmp_path: Path) -> None:
        root = tmp_path / 'fresh-project'
        root.mkdir()

        assert find_issues(root) == []

    def test_univers_missing_entirely_is_valid(self, project_root: Path) -> None:
        shutil.rmtree(project_root / 'univers')

        assert find_issues(project_root) == []

    def test_stories_missing_entirely_is_valid(self, project_root: Path) -> None:
        shutil.rmtree(project_root / 'stories')

        assert find_issues(project_root) == []

    def test_univers_with_no_categories_is_valid(self, project_root: Path) -> None:
        shutil.rmtree(project_root / 'univers' / 'lieux')
        shutil.rmtree(project_root / 'univers' / 'personnages')

        assert find_issues(project_root) == []

    def test_saga_with_no_tomes_is_valid(self, project_root: Path) -> None:
        shutil.rmtree(project_root / 'stories' / 'saga-test' / 'tome-1')

        assert find_issues(project_root) == []

    def test_tome_with_no_acts_is_valid(self, project_root: Path) -> None:
        shutil.rmtree(project_root / 'stories' / 'saga-test' / 'tome-1' / 'act-1')

        assert find_issues(project_root) == []

    def test_act_with_no_chapters_is_valid(self, project_root: Path) -> None:
        chapter_dir = project_root / 'stories' / 'saga-test' / 'tome-1' / 'act-1' / '_chapter'
        for chapter in chapter_dir.iterdir():
            chapter.unlink()

        assert find_issues(project_root) == []

    def test_saga_with_no_arcs_folder_is_valid(self, project_root: Path) -> None:
        shutil.rmtree(project_root / 'stories' / 'saga-test' / 'arcs')

        assert find_issues(project_root) == []

    def test_arcs_folder_is_not_validated_as_a_tome(self, project_root: Path) -> None:
        """A saga's arcs/ folder has no _index.md -- it must never be treated as a tome."""
        assert find_issues(project_root) == []
        assert (project_root / 'stories' / 'saga-test' / 'arcs' / '_index.md').is_file() is False


class TestUniversChecks:
    def test_category_missing_template(self, project_root: Path) -> None:
        (project_root / 'univers' / 'lieux' / '_template.md').unlink()

        issues = find_issues(project_root)

        assert any('lieux' in issue and '_template.md' in issue for issue in issues)

    def test_category_missing_index(self, project_root: Path) -> None:
        (project_root / 'univers' / 'personnages' / '_index.md').unlink()

        issues = find_issues(project_root)

        assert any('personnages' in issue and '_index.md' in issue for issue in issues)


class TestStoriesChecks:
    def test_missing_stories_index(self, project_root: Path) -> None:
        (project_root / 'stories' / '_index.md').unlink()

        issues = find_issues(project_root)

        assert any('stories' in issue and '_index.md' in issue for issue in issues)

    def test_saga_missing_manifest(self, project_root: Path) -> None:
        (project_root / 'stories' / 'saga-test' / '_manifest.md').unlink()

        issues = find_issues(project_root)

        assert any('saga-test' in issue and '_manifest.md' in issue for issue in issues)

    def test_tome_missing_index(self, project_root: Path) -> None:
        (project_root / 'stories' / 'saga-test' / 'tome-1' / '_index.md').unlink()

        issues = find_issues(project_root)

        assert any('tome-1' in issue and '_index.md' in issue for issue in issues)

    def test_act_missing_index(self, project_root: Path) -> None:
        (project_root / 'stories' / 'saga-test' / 'tome-1' / 'act-1' / '_index.md').unlink()

        issues = find_issues(project_root)

        assert any('act-1' in issue and '_index.md' in issue for issue in issues)

    def test_one_shot_missing_index(self, project_root: Path) -> None:
        (project_root / 'stories' / 'one-shot-test' / '_index.md').unlink()

        issues = find_issues(project_root)

        assert any('one-shot-test' in issue and '_index.md' in issue for issue in issues)


class TestMultipleIssues:
    def test_all_broken_pieces_are_reported_together(self, project_root: Path) -> None:
        (project_root / 'stories' / 'saga-test' / '_manifest.md').unlink()
        (project_root / 'univers' / 'lieux' / '_template.md').unlink()

        issues = find_issues(project_root)

        assert len(issues) == 2
