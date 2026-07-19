"""In-place editing of fiches: whole-file edits and targeted section patches.

Every write lands on the markdown file itself (via `ether.univers.repository`);
the DB is refreshed afterwards with a cheap single-file reindex.
"""

from __future__ import annotations

from dataclasses import replace
from typing import Annotated

from fastapi import APIRouter
from fastapi import Form
from fastapi import HTTPException
from fastapi import Request
from fastapi.responses import HTMLResponse
from fastapi.responses import RedirectResponse

from ether.config import get_settings
from ether.db import get_session
from ether.templates import templates
from ether.univers import frontmatter
from ether.univers import repository
from ether.univers.index_models import EtherItem
from ether.univers.indexer import reindex_one

router = APIRouter()


def _split_csv(text: str) -> list[str]:
    return [part.strip() for part in text.split(',') if part.strip()]


def _get_item_or_404(item_id: str) -> EtherItem:
    with get_session() as session:
        item = session.get(EtherItem, item_id)
    if item is None:
        raise HTTPException(status_code=404, detail=f'Unknown item: {item_id}')
    return item


@router.get('/item/{item_id}/edit', response_class=HTMLResponse)
def edit_form(request: Request, item_id: str) -> HTMLResponse:
    """Show the whole-fiche edit form plus the section-patch form."""
    item = _get_item_or_404(item_id)
    settings = get_settings()
    meta, body = frontmatter.parse_file(settings.univers_path / item.relative_path)
    suggested_sections = repository.expected_sections(settings.univers_path, item.category)
    return templates.TemplateResponse(
        request,
        'fiche/edit.html',
        {
            'item': item,
            'meta': meta,
            'body': body,
            'aliases_text': ', '.join(meta.aliases),
            'tags_text': ', '.join(meta.tags),
            'related_text': ', '.join(meta.related),
            'sections': sorted(set(repository.list_sections(body)) | set(suggested_sections)),
        },
    )


@router.post('/item/{item_id}/edit')
def edit_submit(
    item_id: str,
    name: Annotated[str, Form()],
    status: Annotated[str, Form()],
    body: Annotated[str, Form()],
    aliases: Annotated[str, Form()] = '',
    tags: Annotated[str, Form()] = '',
    related: Annotated[str, Form()] = '',
    updated: Annotated[str, Form()] = '',
) -> RedirectResponse:
    """Save a whole-fiche edit: frontmatter fields + full body replacement."""
    item = _get_item_or_404(item_id)
    settings = get_settings()

    current_meta, _current_body = frontmatter.parse_file(
        settings.univers_path / item.relative_path,
    )
    new_meta = replace(
        current_meta,
        name=name,
        status=status,
        aliases=_split_csv(aliases),
        tags=_split_csv(tags),
        related=_split_csv(related),
        updated=updated,
    )
    repository.write_item(settings.univers_path, item.relative_path, new_meta, body)

    with get_session() as session:
        reindex_one(settings.univers_path, item.relative_path, session)

    return RedirectResponse(url=f'/item/{item_id}', status_code=303)


@router.post('/item/{item_id}/section')
def section_submit(
    item_id: str,
    heading: Annotated[str, Form()],
    content: Annotated[str, Form()],
    mode: Annotated[str, Form()] = 'replace',
) -> RedirectResponse:
    """Save a targeted `##` section patch without touching the rest of the body."""
    item = _get_item_or_404(item_id)
    settings = get_settings()

    repository.write_section(
        settings.univers_path,
        item.relative_path,
        heading,
        content,
        mode=mode,
    )

    with get_session() as session:
        reindex_one(settings.univers_path, item.relative_path, session)

    return RedirectResponse(url=f'/item/{item_id}', status_code=303)
