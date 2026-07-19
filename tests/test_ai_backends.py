"""Tests for `ether.ai.backends`."""

from __future__ import annotations

from ether.ai import backends
from ether.ai.prompt_builder import compose_item_context
from ether.config import EtherSettings


def _settings(**overrides: object) -> EtherSettings:
    from pathlib import Path

    base = {
        'univers_path': Path('/nonexistent/univers'),
        'db_path': Path('/nonexistent/ether.db'),
        'style_manifest_path': Path('/nonexistent/univers/_manifest.md'),
        'ai_backend': 'stub',
        'gemini_api_key': None,
        'gemini_model': 'gemini-1.5-flash',
        'anthropic_api_key': None,
        'claude_model': 'claude-sonnet-5',
        'host': '127.0.0.1',
        'port': 8000,
    }
    base.update(overrides)
    return EtherSettings(**base)  # type: ignore[arg-type]


class TestStubBackend:
    def test_echoes_prompt_when_no_skeleton_marker(self) -> None:
        out = backends.StubBackend().generate('some free-form prompt\n\nlast paragraph')

        assert out.startswith('[BACKEND=stub]')
        assert 'last paragraph' in out
        assert '[trace:' in out

    def test_fills_skeleton_placeholders_into_a_parseable_draft(self) -> None:
        prompt = compose_item_context(
            manifest_text='',
            template_skeleton='id: {{slug}}\ntype: personnage\nname: {{Nom}}',
            brief='a new character',
            existing_items=[],
        )

        out = backends.StubBackend().generate(prompt)

        assert out.startswith('id: stub-')
        assert '{{' not in out.split('\n\n[trace:')[0]

    def test_deterministic_for_identical_prompt(self) -> None:
        prompt = 'same prompt every time'
        first = backends.StubBackend().generate(prompt)
        second = backends.StubBackend().generate(prompt)

        assert first.split('\n\n[trace:')[0] == second.split('\n\n[trace:')[0]


class TestGetBackend:
    def test_defaults_to_stub(self) -> None:
        assert isinstance(backends.get_backend(_settings(ai_backend='stub')), backends.StubBackend)

    def test_falls_back_to_stub_when_gemini_key_missing(self) -> None:
        settings = _settings(ai_backend='gemini', gemini_api_key=None)
        assert isinstance(backends.get_backend(settings), backends.StubBackend)

    def test_uses_gemini_when_configured(self) -> None:
        settings = _settings(ai_backend='gemini', gemini_api_key='fake-key')
        assert isinstance(backends.get_backend(settings), backends.GeminiBackend)

    def test_falls_back_to_stub_when_claude_key_missing(self) -> None:
        settings = _settings(ai_backend='claude', anthropic_api_key=None)
        assert isinstance(backends.get_backend(settings), backends.StubBackend)

    def test_uses_claude_when_configured(self) -> None:
        settings = _settings(ai_backend='claude', anthropic_api_key='fake-key')
        assert isinstance(backends.get_backend(settings), backends.ClaudeBackend)
