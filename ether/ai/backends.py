"""Pluggable text-generation backends.

`AI_BACKEND` (see `ether.config`) selects the implementation used by both the
creation panel and prose generation. Defaults to `stub`: no live API call is
ever made unless a backend is explicitly configured.
"""

from __future__ import annotations

import datetime as dt
import hashlib
import re
import time
from typing import TYPE_CHECKING
from typing import Protocol

import httpx

from ether.config import get_settings

if TYPE_CHECKING:  # pragma: no cover
    from ether.config import EtherSettings

_SKELETON_MARKER_RE = re.compile(
    r'\[GABARIT DE LA CAT[ÉE]GORIE\]\n(.*?)\n\n\[',
    re.DOTALL,
)
_PLACEHOLDER_RE = re.compile(r'\{\{.*?\}\}')
_ID_LINE_RE = re.compile(r'(?m)^id:\s*.*$')
_UPDATED_LINE_RE = re.compile(r'(?m)^updated:\s*.*$')


class GenerationBackend(Protocol):
    """Contract every generation backend must satisfy."""

    def generate(self, prompt: str) -> str:
        """Return generated text for `prompt`."""
        ...


def _trace(t0: float, prompt: str, out: str) -> str:
    dt_ms = int((time.perf_counter() - t0) * 1000)
    return f'\n\n[trace: {dt_ms}ms, prompt={len(prompt)}c, out={len(out)}c]'


def _fill_skeleton(prompt: str) -> str | None:
    """Echo back a `compose_item_context` skeleton with placeholders filled in.

    Lets the offline stub backend produce something the creation panel can
    actually parse and save, instead of an unparseable prose echo.
    """
    match = _SKELETON_MARKER_RE.search(prompt)
    if match is None:
        return None
    filled = _PLACEHOLDER_RE.sub('a-completer', match.group(1))
    digest = hashlib.sha1(prompt.encode('utf-8'), usedforsecurity=False)  # nosec B324 - stub id, not a security hash
    suffix = digest.hexdigest()[:8]
    filled = _ID_LINE_RE.sub(f'id: stub-{suffix}', filled, count=1)
    today = dt.date.today().isoformat()  # noqa: DTZ011 - cosmetic placeholder, not a real timestamp
    return _UPDATED_LINE_RE.sub(f'updated: {today}', filled, count=1)


class StubBackend:
    """Deterministic backend used by default and for tests — makes no network calls."""

    def generate(self, prompt: str) -> str:
        """Return a predictable, parseable draft (see `_fill_skeleton`) or a prompt echo."""
        t0 = time.perf_counter()
        skeleton_draft = _fill_skeleton(prompt)
        out = (
            skeleton_draft
            if skeleton_draft is not None
            else ('[BACKEND=stub]\n' + prompt.strip().split('\n\n')[-1][:200])
        )
        return out + _trace(t0, prompt, out)


class GeminiBackend:
    """Client for the Gemini API (Google AI)."""

    def __init__(self, api_key: str, model: str) -> None:
        """Store the API key and model used for every `generate()` call."""
        self.api_key = api_key
        self.model = model
        base = 'https://generativelanguage.googleapis.com/v1beta/models'
        self._endpoint = f'{base}/{model}:generateContent'

    def generate(self, prompt: str) -> str:  # pragma: no cover - network call
        """Call the Gemini API and return its text output."""
        t0 = time.perf_counter()
        headers = {'Content-Type': 'application/json'}
        params = {'key': self.api_key}
        payload = {'contents': [{'parts': [{'text': prompt}]}]}
        try:
            with httpx.Client(timeout=30) as client:
                response = client.post(
                    self._endpoint,
                    headers=headers,
                    params=params,
                    json=payload,
                )
            response.raise_for_status()
        except httpx.HTTPError as exc:
            return f'(Erreur backend Gemini : {exc})'
        data = response.json()
        candidates = data.get('candidates') or []
        if candidates:
            parts = candidates[0].get('content', {}).get('parts', [])
            if parts:
                out = parts[0].get('text', '(vide)')
                return out + _trace(t0, prompt, out)
        return '(Aucune sortie générée)' + _trace(t0, prompt, '')


class ClaudeBackend:
    """Client for the Anthropic Messages API, via raw httpx (no SDK dependency)."""

    _ENDPOINT = 'https://api.anthropic.com/v1/messages'
    _API_VERSION = '2023-06-01'

    def __init__(self, api_key: str, model: str) -> None:
        """Store the API key and model used for every `generate()` call."""
        self.api_key = api_key
        self.model = model

    def generate(self, prompt: str) -> str:  # pragma: no cover - network call
        """Call the Anthropic Messages API and return its text output."""
        t0 = time.perf_counter()
        headers = {
            'x-api-key': self.api_key,
            'anthropic-version': self._API_VERSION,
            'content-type': 'application/json',
        }
        payload = {
            'model': self.model,
            'max_tokens': 4096,
            'messages': [{'role': 'user', 'content': prompt}],
        }
        try:
            with httpx.Client(timeout=60) as client:
                response = client.post(self._ENDPOINT, headers=headers, json=payload)
            response.raise_for_status()
        except httpx.HTTPError as exc:
            return f'(Erreur backend Claude : {exc})'
        data = response.json()
        blocks = data.get('content') or []
        texts = [block.get('text', '') for block in blocks if block.get('type') == 'text']
        out = ''.join(texts) or '(Aucune sortie générée)'
        return out + _trace(t0, prompt, out)


def get_backend(settings: EtherSettings | None = None) -> GenerationBackend:
    """Resolve the configured backend (`stub` by default, never a silent live call)."""
    settings = settings or get_settings()
    if settings.ai_backend == 'gemini' and settings.gemini_api_key:
        return GeminiBackend(api_key=settings.gemini_api_key, model=settings.gemini_model)
    if settings.ai_backend == 'claude' and settings.anthropic_api_key:
        return ClaudeBackend(api_key=settings.anthropic_api_key, model=settings.claude_model)
    return StubBackend()
