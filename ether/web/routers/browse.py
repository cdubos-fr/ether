"""Read-only browsing of the indexed univers: categories, listings, item detail."""

from __future__ import annotations

import json
from pathlib import Path
from typing import TypedDict

from fastapi import APIRouter
from fastapi import HTTPException
from fastapi import Request
from fastapi.responses import HTMLResponse
from sqlmodel import select

from ether.config import get_settings
from ether.db import get_session
from ether.templates import templates
from ether.univers import frontmatter
from ether.univers.index_models import EtherItem
from ether.univers.indexer import backlinks
from ether.univers.indexer import outgoing_links
from ether.univers.indexer import path_index
from ether.univers.linkrewrite import rewrite_relative_links

router = APIRouter()


class ItemView(TypedDict):
    """Template context shared by category listings and fiche detail."""

    item: EtherItem
    aliases: list[str]
    tags: list[str]


def _item_view(item: EtherItem) -> ItemView:
    return ItemView(
        item=item,
        aliases=json.loads(item.aliases_json),
        tags=json.loads(item.tags_json),
    )


@router.get('/', response_class=HTMLResponse)
def index(request: Request) -> HTMLResponse:
    """Landing page: categories with item counts."""
    with get_session() as session:
        items = session.exec(select(EtherItem)).all()
    categories: dict[str, int] = {}
    for item in items:
        categories[item.category] = categories.get(item.category, 0) + 1
    return templates.TemplateResponse(
        request,
        'browse/index.html',
        {
            'categories': sorted(categories.items()),
            'total_items': len(items),
            'univers_path': str(get_settings().univers_path),
        },
    )


@router.get('/browse/{category}', response_class=HTMLResponse)
def browse_category(request: Request, category: str) -> HTMLResponse:
    """List every fiche indexed under a category."""
    with get_session() as session:
        items = session.exec(
            select(EtherItem).where(EtherItem.category == category).order_by(EtherItem.name),
        ).all()
    if not items:
        raise HTTPException(status_code=404, detail=f'Unknown category: {category}')
    return templates.TemplateResponse(
        request,
        'browse/category.html',
        {'category': category, 'items': [_item_view(i) for i in items]},
    )


@router.get('/item/{item_id}', response_class=HTMLResponse)
def item_detail(request: Request, item_id: str) -> HTMLResponse:
    """Fiche detail: rendered body, outgoing related links, and computed backlinks."""
    settings = get_settings()
    with get_session() as session:
        item = session.get(EtherItem, item_id)
        if item is None:
            raise HTTPException(status_code=404, detail=f'Unknown item: {item_id}')
        out_links = outgoing_links(session, item_id)
        back_ids = backlinks(session, item_id)
        wanted_ids = {lnk.target_id for lnk in out_links} | set(back_ids)
        query = select(EtherItem).where(EtherItem.id.in_(wanted_ids))  # type: ignore[attr-defined]  # ty:ignore[unresolved-attribute]
        related_items = {i.id: i for i in session.exec(query).all()}
        paths = path_index(session)

    _, body = frontmatter.parse_file(settings.univers_path / item.relative_path)
    body = rewrite_relative_links(body, Path(item.relative_path), paths)

    return templates.TemplateResponse(
        request,
        'browse/item.html',
        {
            **_item_view(item),
            'body': body,
            'outgoing': [
                {'target_id': lnk.target_id, 'item': related_items.get(lnk.target_id)}
                for lnk in out_links
            ],
            'backlinks': [{'source_id': bid, 'item': related_items.get(bid)} for bid in back_ids],
        },
    )
