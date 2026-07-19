"""Tests for `ether.univers.frontmatter`, especially write-path formatting fidelity."""

from __future__ import annotations

from dataclasses import replace
from typing import TYPE_CHECKING

import pytest

from ether.univers import frontmatter

if TYPE_CHECKING:  # pragma: no cover
    from pathlib import Path


class TestParsing:
    def test_parse_file_reads_frontmatter_and_body(self, univers_root: Path) -> None:
        meta, body = frontmatter.parse_file(univers_root / 'personnages' / 'hero.md')

        assert meta.id == 'hero'
        assert meta.type == 'personnage'
        assert meta.related == ['sidekick', 'citadel']
        assert '# Hero' in body

    def test_parse_file_missing_required_field_raises(self, tmp_path: Path) -> None:
        path = tmp_path / 'bad.md'
        path.write_text('---\nname: "No id or type"\n---\n\nbody', encoding='utf-8')

        with pytest.raises(frontmatter.FrontmatterError, match='id, type'):
            frontmatter.parse_file(path)

    def test_split_frontmatter_requires_fence(self) -> None:
        with pytest.raises(frontmatter.FrontmatterError):
            frontmatter.split_frontmatter('no fence here')


class TestWriteRoundTrip:
    def test_editing_one_field_leaves_others_byte_identical_in_style(
        self,
        univers_root: Path,
    ) -> None:
        path = univers_root / 'personnages' / 'hero.md'
        before = path.read_text(encoding='utf-8')

        raw, body = frontmatter.load_raw(path)
        raw['status'] = 'theorise'
        frontmatter.write_file(path, raw, body)

        after = path.read_text(encoding='utf-8')
        assert 'status: theorise' in after
        assert 'status: canon' not in after
        # Flow-style arrays and unquoted dates must survive untouched.
        assert 'tags: [protagoniste]' in after
        assert 'related: [sidekick, citadel]' in after
        assert 'updated: 2026-01-01' in after
        # Only the status line should differ from the original.
        before_lines = before.splitlines()
        after_lines = after.splitlines()
        changed = [b for b, a in zip(before_lines, after_lines, strict=True) if b != a]
        assert changed == ['status: canon']

    def test_flow_seq_preserves_flow_style_on_mutation(self, univers_root: Path) -> None:
        path = univers_root / 'personnages' / 'hero.md'
        raw, body = frontmatter.load_raw(path)

        raw['tags'] = frontmatter.flow_seq(raw.get('tags'), ['protagoniste', 'brave'])
        frontmatter.write_file(path, raw, body)

        after = path.read_text(encoding='utf-8')
        assert 'tags: [protagoniste, brave]' in after

    def test_coerce_date_returns_native_date_for_iso_string(self) -> None:
        import datetime as dt

        assert frontmatter.coerce_date('2026-07-19') == dt.date(2026, 7, 19)
        assert frontmatter.coerce_date('not-a-date') == 'not-a-date'

    def test_new_frontmatter_mapping_uses_conventional_field_order(
        self,
        univers_root: Path,
    ) -> None:
        meta, _ = frontmatter.parse_file(univers_root / 'personnages' / 'hero.md')
        new_meta = replace(meta, id='new-hero')

        mapping = frontmatter.new_frontmatter_mapping(new_meta)

        assert list(mapping.keys()) == [
            'id',
            'type',
            'name',
            'aliases',
            'status',
            'tags',
            'related',
            'updated',
        ]

    def test_write_file_then_parse_file_round_trips(self, tmp_path: Path) -> None:
        from ether.univers.schema import FicheFrontmatter

        meta = FicheFrontmatter(
            id='new-item',
            type='personnage',
            name='New Item',
            related=['hero'],
            updated='2026-07-19',
        )
        path = tmp_path / 'new-item.md'
        frontmatter.write_file(path, frontmatter.new_frontmatter_mapping(meta), '# New Item\n')

        reparsed_meta, reparsed_body = frontmatter.parse_file(path)
        assert reparsed_meta.id == 'new-item'
        assert reparsed_meta.related == ['hero']
        assert '# New Item' in reparsed_body
