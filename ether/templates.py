"""Jinja2 template environment: globals and filters shared by every page."""

from __future__ import annotations

from datetime import UTC
from datetime import datetime

import markdown as _markdown
from fastapi.templating import Jinja2Templates
from markupsafe import Markup

from ether.paths import TEMPLATES_DIR

_MD = _markdown.Markdown(extensions=['extra', 'sane_lists'])


def render_markdown(text: str) -> Markup:
    """Render an author-authored markdown body to HTML for template embedding."""
    _MD.reset()
    # ether is a single-user local tool: rendered text is always this same user's own
    # fiche/manuscript content (their files or their own AI-generation requests), never
    # another party's input, so there is no cross-user stored-XSS boundary to cross.
    return Markup(_MD.convert(text))  # noqa: S704  # nosec B704


def _now() -> datetime:
    return datetime.now(UTC)


templates = Jinja2Templates(directory=str(TEMPLATES_DIR))
templates.env.filters['markdown'] = render_markdown
templates.env.globals.update({'now': _now})  # ty:ignore[no-matching-overload]
