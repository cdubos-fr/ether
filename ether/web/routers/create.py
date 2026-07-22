"""AI-assisted creation panel: draft a new fiche, or a new/edited section.

Nothing is written to disk until the human reviews and explicitly saves the
generated draft — generation only ever populates the review textarea.
"""

from __future__ import annotations

from pathlib import Path
from typing import Annotated

from fastapi import APIRouter
from fastapi import Form
from fastapi import HTTPException
from fastapi import Request
from fastapi.responses import HTMLResponse
from fastapi.responses import RedirectResponse
from sqlmodel import select

from ether.ai.backends import get_backend
from ether.ai.prompt_builder import compose_item_context
from ether.ai.prompt_builder import compose_section_context
from ether.ai.style_manifest import read_manifest
from ether.config import get_settings
from ether.db import get_session
from ether.templates import templates
from ether.univers import frontmatter
from ether.univers import repository
from ether.univers.frontmatter import FrontmatterError
from ether.univers.index_models import EtherItem
from ether.univers.indexer import reindex_one
from ether.univers.scanner import find_template
from ether.univers.scanner import list_categories
from ether.univers.scanner import read_template_skeleton
from ether.univers.schema import FicheFrontmatter

router = APIRouter()

_DEFAULT_TEMPLATE = """# Template : fiche de {nom}

```yaml
---
id: {{{{slug-unique}}}}
type: {type_fiche}
name: "{{{{Nom}}}}"
aliases: []
status: brouillon
tags: []
related: []
updated: {{{{AAAA-MM-JJ}}}}
---
```

```markdown
# {{{{Nom}}}}

## Description

{{{{À quoi ressemble/qui est ce {nom}.}}}}

## Voir aussi

- {{{{liens vers fiches liées}}}}
```
"""


def _get_item_or_404(item_id: str) -> EtherItem:
    with get_session() as session:
        item = session.get(EtherItem, item_id)
    if item is None:
        raise HTTPException(status_code=404, detail=f'Unknown item: {item_id}')
    return item


@router.get('/create', response_class=HTMLResponse)
def create_index(request: Request) -> HTMLResponse:
    """List categories and existing items (grouped by category) for AI-assisted creation."""
    settings = get_settings()
    categories = list_categories(settings.univers_path)
    with get_session() as session:
        items = list(session.exec(select(EtherItem).order_by(EtherItem.name)))
    items_by_category: dict[str, list[EtherItem]] = {}
    for item in items:
        items_by_category.setdefault(item.category, []).append(item)
    return templates.TemplateResponse(
        request,
        'create/index.html',
        {'categories': categories, 'items_by_category': sorted(items_by_category.items())},
    )


@router.post('/create')
def create_category(
    slug: Annotated[str, Form()],
    nom: Annotated[str, Form()],
    type_fiche: Annotated[str, Form()],
) -> RedirectResponse:
    """Create a new univers category: its folder + a scaffolded `_index.md` and `_template.md`."""
    settings = get_settings()
    category_path = settings.univers_path / slug
    if category_path.exists():
        raise HTTPException(status_code=409, detail=f'{slug} already exists')
    category_path.mkdir(parents=True)

    index_meta = FicheFrontmatter(id=f'{slug}-index', type='concept', name=nom, tags=['index'])
    relative_path = str(Path(slug) / '_index.md')
    repository.write_item(settings.univers_path, relative_path, index_meta, f'# {nom}\n')
    (category_path / '_template.md').write_text(
        _DEFAULT_TEMPLATE.format(nom=nom, type_fiche=type_fiche),
        encoding='utf-8',
    )

    with get_session() as session:
        reindex_one(settings.univers_path, relative_path, session)

    return RedirectResponse(url=f'/create/{slug}', status_code=303)


@router.get('/create/{category}', response_class=HTMLResponse)
def create_form(request: Request, category: str) -> HTMLResponse:
    """Show the new-fiche creation form for a category."""
    settings = get_settings()
    if find_template(settings.univers_path, category) is None:
        raise HTTPException(status_code=404, detail=f'No _template.md for category: {category}')
    return templates.TemplateResponse(
        request,
        'create/panel.html',
        {'category': category, 'brief': '', 'draft': ''},
    )


@router.post('/create/{category}/generate', response_class=HTMLResponse)
def create_generate(
    request: Request,
    category: str,
    brief: Annotated[str, Form()],
) -> HTMLResponse:
    """Ask the configured AI backend to draft a new fiche for this category."""
    settings = get_settings()
    template_path = find_template(settings.univers_path, category)
    if template_path is None:
        raise HTTPException(status_code=404, detail=f'No _template.md for category: {category}')

    with get_session() as session:
        existing = list(
            session.exec(select(EtherItem).where(EtherItem.category == category)),
        )

    prompt = compose_item_context(
        manifest_text=read_manifest(settings.manifest_path_for(settings.default_saga)),
        template_skeleton=read_template_skeleton(template_path),
        brief=brief,
        existing_items=existing,
    )
    draft = get_backend().generate(prompt)

    return templates.TemplateResponse(
        request,
        'create/panel.html',
        {'category': category, 'brief': brief, 'draft': draft},
    )


@router.post('/create/{category}/save')
def create_save(category: str, draft: Annotated[str, Form()]) -> RedirectResponse:
    """Parse the (human-reviewed) draft as a fiche and write it as a new file."""
    settings = get_settings()
    try:
        meta, body = frontmatter.parse_text(draft)
    except FrontmatterError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc

    relative_path = str(Path(category) / f'{meta.id}.md')
    full_path = settings.univers_path / relative_path
    if full_path.exists():
        raise HTTPException(status_code=409, detail=f'{relative_path} already exists')

    repository.write_item(settings.univers_path, relative_path, meta, body)
    with get_session() as session:
        reindex_one(settings.univers_path, relative_path, session)

    return RedirectResponse(url=f'/item/{meta.id}', status_code=303)


@router.get('/item/{item_id}/create-section', response_class=HTMLResponse)
def create_section_form(request: Request, item_id: str) -> HTMLResponse:
    """Show the AI-assisted section drafting form for an existing fiche."""
    item = _get_item_or_404(item_id)
    return templates.TemplateResponse(
        request,
        'create/section.html',
        {'item': item, 'heading': '', 'brief': '', 'draft': ''},
    )


@router.post('/item/{item_id}/create-section/generate', response_class=HTMLResponse)
def create_section_generate(
    request: Request,
    item_id: str,
    heading: Annotated[str, Form()],
    brief: Annotated[str, Form()],
) -> HTMLResponse:
    """Ask the configured AI backend to draft one section of an existing fiche."""
    item = _get_item_or_404(item_id)
    settings = get_settings()

    prompt = compose_section_context(
        manifest_text=read_manifest(settings.manifest_path_for(settings.default_saga)),
        item=item,
        heading=heading,
        brief=brief,
    )
    draft = get_backend().generate(prompt)

    return templates.TemplateResponse(
        request,
        'create/section.html',
        {'item': item, 'heading': heading, 'brief': brief, 'draft': draft},
    )


@router.post('/item/{item_id}/create-section/save')
def create_section_save(
    item_id: str,
    heading: Annotated[str, Form()],
    draft: Annotated[str, Form()],
    mode: Annotated[str, Form()] = 'replace',
) -> RedirectResponse:
    """Save the (human-reviewed) section draft into the fiche via a targeted patch."""
    item = _get_item_or_404(item_id)
    settings = get_settings()

    repository.write_section(settings.univers_path, item.relative_path, heading, draft, mode=mode)
    with get_session() as session:
        reindex_one(settings.univers_path, item.relative_path, session)

    return RedirectResponse(url=f'/item/{item_id}', status_code=303)
