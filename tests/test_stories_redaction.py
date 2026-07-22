"""Tests for `ether.stories.redaction` and the `/stories/.../redact` routes."""

from __future__ import annotations

import html
import re
from typing import TYPE_CHECKING

if TYPE_CHECKING:  # pragma: no cover
    from fastapi.testclient import TestClient

_DRAFT_RE = re.compile(r'<textarea name="draft"[^>]*>(.*)</textarea>', re.DOTALL)

_CHAPTER_ID = 'saga-test-tome-1-act-1-chapitre-1'


def _extract_draft(html_text: str) -> str:
    match = _DRAFT_RE.search(html_text)
    assert match is not None
    return html.unescape(match.group(1))


class TestComposeRedactionContext:
    def test_pulls_linked_fiches_manifest_and_body_tail(
        self,
        stories_indexed: None,
        indexed: None,
    ) -> None:
        from ether.config import get_settings
        from ether.db import get_session
        from ether.stories.redaction import compose_redaction_context

        with get_session() as session:
            ctx = compose_redaction_context(
                session,
                get_settings(),
                _CHAPTER_ID,
                instruction='Écris la suite.',
                contraintes='',
            )

        assert {f.id for f in ctx.fiches_liees} == {'hero'}
        assert ctx.instruction == 'Écris la suite.'
        assert 'Corps du chapitre' in ctx.corps_actuel_tail

    def test_unknown_chapter_raises(self, stories_indexed: None) -> None:
        import pytest

        from ether.config import get_settings
        from ether.db import get_session
        from ether.stories.redaction import RedactionError
        from ether.stories.redaction import compose_redaction_context

        with get_session() as session, pytest.raises(RedactionError):
            compose_redaction_context(session, get_settings(), 'nonexistent', 'x', '')


class TestRedactionRoutes:
    def test_generate_then_append_persists_prose(self, client: TestClient) -> None:
        generated = client.post(
            f'/stories/chapters/{_CHAPTER_ID}/redact/generate',
            data={'instruction': 'Une révélation.', 'contraintes': 'Pas de dialogue.'},
        )
        assert generated.status_code == 200
        draft = _extract_draft(generated.text)

        appended = client.post(
            f'/stories/chapters/{_CHAPTER_ID}/redact/append',
            data={'draft': draft},
            follow_redirects=False,
        )
        assert appended.status_code == 303

        from ether.config import get_settings
        from ether.stories.frontmatter import parse_file

        settings = get_settings()
        chapter_path = (
            settings.stories_path / 'saga-test' / 'tome-1' / 'act-1' / '_chapter' / 'chapitre-1.md'
        )
        _, body = parse_file(chapter_path)
        assert '***' in body
        assert draft.strip() in body

    def test_unknown_chapter_is_404(self, client: TestClient) -> None:
        assert client.get('/stories/chapters/nonexistent').status_code == 404
