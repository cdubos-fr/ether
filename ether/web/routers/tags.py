"""Cross-cutting tag navigation: browse fiches by tag, independent of category.

Categories organize the univers repo by folder (personnages, lieux, ...);
tags cut across that (e.g. every kinésie sharing a Jungian function, `fi`),
which a folder-based browse can't express.
"""

from __future__ import annotations

from fastapi import APIRouter
from fastapi import HTTPException
from fastapi import Request
from fastapi.responses import HTMLResponse

from ether.db import get_session
from ether.templates import templates
from ether.univers.indexer import items_with_tag
from ether.univers.indexer import list_tags

router = APIRouter()


@router.get('/tags', response_class=HTMLResponse)
def tags_index(request: Request) -> HTMLResponse:
    """List every tag in use, with counts."""
    with get_session() as session:
        tags = list_tags(session)
    return templates.TemplateResponse(request, 'tags/index.html', {'tags': tags})


@router.get('/tags/{tag}', response_class=HTMLResponse)
def tag_detail(request: Request, tag: str) -> HTMLResponse:
    """List every fiche carrying `tag`, across all categories."""
    with get_session() as session:
        items = items_with_tag(session, tag)
    if not items:
        raise HTTPException(status_code=404, detail=f'Unknown tag: {tag}')
    return templates.TemplateResponse(request, 'tags/tag.html', {'tag': tag, 'items': items})
