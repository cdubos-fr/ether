"""Tests for `ether.univers.linkrewrite`."""

from __future__ import annotations

from pathlib import Path

from ether.univers.linkrewrite import rewrite_relative_links


class TestRewriteRelativeLinks:
    def test_rewrites_same_directory_link(self) -> None:
        body = '- [Sidekick](sidekick.md)'
        paths = {'personnages/sidekick.md': 'sidekick'}

        rewritten = rewrite_relative_links(body, Path('personnages/hero.md'), paths)

        assert rewritten == '- [Sidekick](/item/sidekick)'

    def test_rewrites_cross_directory_link(self) -> None:
        body = 'Voir [Citadel](../lieux/citadel.md) pour plus de détails.'
        paths = {'lieux/citadel.md': 'citadel'}

        rewritten = rewrite_relative_links(body, Path('personnages/hero.md'), paths)

        assert rewritten == 'Voir [Citadel](/item/citadel) pour plus de détails.'

    def test_preserves_fragment(self) -> None:
        body = '[Gouvernance](../organisations/le-concile/_index.md#gouvernance)'
        paths = {'organisations/le-concile/_index.md': 'le-concile'}

        rewritten = rewrite_relative_links(body, Path('personnages/hero.md'), paths)

        assert rewritten == '[Gouvernance](/item/le-concile#gouvernance)'

    def test_leaves_unresolvable_links_untouched(self) -> None:
        body = '[Nowhere](../nowhere/ghost.md)'

        rewritten = rewrite_relative_links(body, Path('personnages/hero.md'), {})

        assert rewritten == body

    def test_leaves_non_markdown_links_untouched(self) -> None:
        body = '[External](https://example.com) and [image](pic.png)'

        rewritten = rewrite_relative_links(body, Path('personnages/hero.md'), {})

        assert rewritten == body

    def test_leaves_images_untouched(self) -> None:
        body = '![diagram](../assets/diagram.md)'
        paths = {'assets/diagram.md': 'diagram'}

        rewritten = rewrite_relative_links(body, Path('personnages/hero.md'), paths)

        assert rewritten == body
