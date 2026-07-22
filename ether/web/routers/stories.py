"""Browse, create and edit sagas/one-shots -> tomes -> acts -> chapters, plus AI scene generation.

Replaces the old DB-only `/sequencer` + `/redaction`: every level is a
markdown file (see `ether.stories`), edited in place the same way univers
fiches are (`ether.web.routers.fiche_edit`). Listings read the filesystem
directly rather than the DB index — a saga/tome/act's *children* aren't
reliably reconstructable from `EtherStoryItem` alone (an index row doesn't
record which level it belongs to), whereas a *specific* row's own id always
resolves unambiguously to its file.
"""

from __future__ import annotations

from dataclasses import replace
from pathlib import Path
from typing import TYPE_CHECKING
from typing import Annotated

from fastapi import APIRouter
from fastapi import Form
from fastapi import HTTPException
from fastapi import Request
from fastapi.responses import HTMLResponse
from fastapi.responses import RedirectResponse

from ether.ai.style_manifest import ensure_manifest
from ether.config import get_settings
from ether.db import get_session
from ether.project import ARCS_DIRNAME
from ether.project import CHAPTER_DIRNAME
from ether.project import INDEX_FILENAME
from ether.project import is_act_folder
from ether.project import is_one_shot
from ether.stories import frontmatter
from ether.stories import repository
from ether.stories.index_models import EtherStoryItem
from ether.stories.indexer import reindex_one
from ether.stories.redaction import append_scene
from ether.stories.redaction import compose_redaction_context
from ether.stories.redaction import generate_prose
from ether.stories.redaction import render_prompt
from ether.stories.schema import StoryFrontmatter
from ether.templates import templates

if TYPE_CHECKING:  # pragma: no cover
    from collections.abc import Callable

    from ether.config import EtherSettings

router = APIRouter(prefix='/stories')


def _split_csv(text: str) -> list[str]:
    return [part.strip() for part in text.split(',') if part.strip()]


def _story_path(settings: EtherSettings, saga: str) -> Path:
    path = settings.stories_path / saga
    if not path.is_dir():
        raise HTTPException(status_code=404, detail=f'Unknown saga: {saga}')
    return path


def _read_node(path: Path) -> StoryFrontmatter | None:
    if not path.is_file():
        return None
    meta, _ = frontmatter.parse_file(path)
    return meta


def _list_dir_nodes(
    parent: Path,
    predicate: Callable[[Path], bool],
) -> list[tuple[str, StoryFrontmatter]]:
    """List (dirname, meta) per child dir of `parent` matching `predicate`, sorted by numero."""
    results: list[tuple[str, StoryFrontmatter]] = []
    for child in sorted(p for p in parent.iterdir() if p.is_dir()):
        if not predicate(child):
            continue
        meta = _read_node(child / INDEX_FILENAME)
        if meta is not None:
            results.append((child.name, meta))
    results.sort(key=lambda pair: (pair[1].numero, pair[0]))
    return results


def _list_chapters(act_dir: Path) -> list[StoryFrontmatter]:
    chapter_dir = act_dir / CHAPTER_DIRNAME
    if not chapter_dir.is_dir():
        return []
    nodes = (_read_node(p) for p in sorted(chapter_dir.glob('*.md')))
    metas = [meta for meta in nodes if meta is not None]
    metas.sort(key=lambda meta: meta.numero)
    return metas


def _list_arcs(story_path: Path) -> list[StoryFrontmatter]:
    arcs_dir = story_path / ARCS_DIRNAME
    if not arcs_dir.is_dir():
        return []
    nodes = (_read_node(p) for p in sorted(arcs_dir.glob('*.md')))
    metas = [meta for meta in nodes if meta is not None]
    metas.sort(key=lambda meta: meta.name)
    return metas


def _get_story_item_or_404(item_id: str) -> EtherStoryItem:
    with get_session() as session:
        item = session.get(EtherStoryItem, item_id)
    if item is None:
        raise HTTPException(status_code=404, detail=f'Unknown story item: {item_id}')
    return item


def _create_act(
    settings: EtherSettings,
    parent_path: Path,
    saga: str,
    tome: str,
    slug: str,
    numero: int,
    titre: str,
    fonction_narrative: str,
) -> str:
    act_path = parent_path / slug
    if act_path.exists():
        raise HTTPException(status_code=409, detail=f'{slug} already exists')
    act_path.mkdir(parents=True)
    (act_path / CHAPTER_DIRNAME).mkdir()
    meta = StoryFrontmatter(
        id=slug,
        type='acte',
        name=titre,
        numero=numero,
        fonction_narrative=fonction_narrative,
    )
    relative = act_path.relative_to(settings.stories_path) / INDEX_FILENAME
    repository.write_node(settings.stories_path, str(relative), meta, f'# {titre}\n')
    with get_session() as session:
        reindex_one(settings.stories_path, str(relative), saga, tome, session)
    return slug


@router.get('', response_class=HTMLResponse)
def stories_index(request: Request) -> HTMLResponse:
    """List every saga/one-shot, plus a form to create a new one."""
    settings = get_settings()
    sagas: list[dict[str, str]] = []
    if settings.stories_path.is_dir():
        for child in sorted(p for p in settings.stories_path.iterdir() if p.is_dir()):
            sagas.append({'slug': child.name, 'kind': 'one-shot' if is_one_shot(child) else 'saga'})
    return templates.TemplateResponse(request, 'stories/index.html', {'sagas': sagas})


@router.post('')
def create_saga(
    slug: Annotated[str, Form()],
    nom: Annotated[str, Form()],
    kind: Annotated[str, Form()] = 'saga',
) -> RedirectResponse:
    """Create a new saga or one-shot: its folder + a scaffolded style manifest."""
    settings = get_settings()
    story_path = settings.stories_path / slug
    if story_path.exists():
        raise HTTPException(status_code=409, detail=f'{slug} already exists')
    story_path.mkdir(parents=True)
    ensure_manifest(story_path / '_manifest.md', nom)

    if kind == 'one-shot':
        meta = StoryFrontmatter(id=slug, type='one-shot', name=nom)
        relative = Path(slug) / INDEX_FILENAME
        repository.write_node(settings.stories_path, str(relative), meta, f'# {nom}\n')
        with get_session() as session:
            reindex_one(settings.stories_path, str(relative), slug, '', session)

    return RedirectResponse(url=f'/stories/{slug}', status_code=303)


@router.get('/{saga}', response_class=HTMLResponse)
def saga_detail(request: Request, saga: str) -> HTMLResponse:
    """Saga detail: its tomes; or one-shot detail: its acts directly."""
    settings = get_settings()
    story_path = _story_path(settings, saga)
    one_shot = is_one_shot(story_path)
    if one_shot:
        acts = _list_dir_nodes(story_path, is_act_folder)
        tomes: list[tuple[str, StoryFrontmatter]] = []
    else:
        tomes = _list_dir_nodes(story_path, lambda _d: True)
        acts = []
    return templates.TemplateResponse(
        request,
        'stories/saga.html',
        {
            'saga': saga,
            'one_shot': one_shot,
            'tomes': tomes,
            'acts': acts,
            'arc_count': len(_list_arcs(story_path)),
        },
    )


@router.post('/{saga}/tomes')
def create_tome(
    saga: str,
    slug: Annotated[str, Form()],
    numero: Annotated[int, Form()],
    titre: Annotated[str, Form()],
    theme_specifique: Annotated[str, Form()] = '',
    question_centrale: Annotated[str, Form()] = '',
) -> RedirectResponse:
    """Create a new tome under a saga."""
    settings = get_settings()
    story_path = _story_path(settings, saga)
    if is_one_shot(story_path):
        raise HTTPException(status_code=400, detail=f'{saga} is a one-shot: it has no tomes')
    tome_path = story_path / slug
    if tome_path.exists():
        raise HTTPException(status_code=409, detail=f'{slug} already exists')
    tome_path.mkdir(parents=True)
    meta = StoryFrontmatter(
        id=slug,
        type='tome',
        name=titre,
        numero=numero,
        theme_specifique=theme_specifique,
        question_centrale=question_centrale,
    )
    relative = Path(saga) / slug / INDEX_FILENAME
    repository.write_node(settings.stories_path, str(relative), meta, f'# {titre}\n')
    with get_session() as session:
        reindex_one(settings.stories_path, str(relative), saga, slug, session)
    return RedirectResponse(url=f'/stories/{saga}', status_code=303)


@router.post('/{saga}/actes')
def create_act_under_saga(
    saga: str,
    slug: Annotated[str, Form()],
    numero: Annotated[int, Form()],
    titre: Annotated[str, Form()],
    fonction_narrative: Annotated[str, Form()] = '',
) -> RedirectResponse:
    """Create a new act directly under a one-shot (or a brand-new, still-empty story)."""
    settings = get_settings()
    story_path = _story_path(settings, saga)
    existing_dirs = [d for d in story_path.iterdir() if d.is_dir()]
    if existing_dirs and not is_one_shot(story_path):
        msg = f'{saga} already has tomes: create acts under a tome instead'
        raise HTTPException(status_code=400, detail=msg)
    _create_act(settings, story_path, saga, '', slug, numero, titre, fonction_narrative)
    return RedirectResponse(url=f'/stories/{saga}', status_code=303)


@router.get('/{saga}/arcs', response_class=HTMLResponse)
def arcs_index(request: Request, saga: str) -> HTMLResponse:
    """List every arc-narratif attached to this saga/one-shot, plus a create form."""
    settings = get_settings()
    story_path = _story_path(settings, saga)
    arcs = _list_arcs(story_path)
    return templates.TemplateResponse(request, 'stories/arcs.html', {'saga': saga, 'arcs': arcs})


@router.post('/{saga}/arcs')
def create_arc(
    saga: str,
    slug: Annotated[str, Form()],
    titre: Annotated[str, Form()],
    type_fiche: Annotated[str, Form()] = 'arc-personnage',
    scope: Annotated[str, Form()] = '',
    related: Annotated[str, Form()] = '',
) -> RedirectResponse:
    """Create a new arc-narratif, scoped to the whole saga/one-shot or to a narrower id."""
    settings = get_settings()
    story_path = _story_path(settings, saga)
    arc_path = story_path / ARCS_DIRNAME / f'{slug}.md'
    if arc_path.exists():
        raise HTTPException(status_code=409, detail=f'{slug} already exists')
    meta = StoryFrontmatter(
        id=slug,
        type=type_fiche,
        name=titre,
        scope=scope,
        related=_split_csv(related),
    )
    relative = arc_path.relative_to(settings.stories_path)
    repository.write_node(settings.stories_path, str(relative), meta, '')
    with get_session() as session:
        reindex_one(settings.stories_path, str(relative), saga, '', session)
    return RedirectResponse(url=f'/stories/arcs/{slug}', status_code=303)


@router.get('/arcs/{arc_id}', response_class=HTMLResponse)
def arc_detail(request: Request, arc_id: str) -> HTMLResponse:
    """Arc detail: rendered body."""
    item = _get_story_item_or_404(arc_id)
    settings = get_settings()
    _, body = frontmatter.parse_file(settings.stories_path / item.relative_path)
    return templates.TemplateResponse(
        request,
        'stories/arc_detail.html',
        {'arc': item, 'body': body},
    )


@router.get('/arcs/{arc_id}/edit', response_class=HTMLResponse)
def arc_edit_form(request: Request, arc_id: str) -> HTMLResponse:
    """Whole-arc edit form: type/scope/related + body."""
    item = _get_story_item_or_404(arc_id)
    settings = get_settings()
    meta, body = frontmatter.parse_file(settings.stories_path / item.relative_path)
    return templates.TemplateResponse(
        request,
        'stories/arc_edit.html',
        {'arc': item, 'meta': meta, 'body': body, 'related_text': ', '.join(meta.related)},
    )


@router.post('/arcs/{arc_id}/edit')
def arc_edit_submit(
    arc_id: str,
    titre: Annotated[str, Form()],
    type_fiche: Annotated[str, Form()],
    statut: Annotated[str, Form()],
    body: Annotated[str, Form()],
    scope: Annotated[str, Form()] = '',
    related: Annotated[str, Form()] = '',
) -> RedirectResponse:
    """Save a whole-arc edit: type/scope/related fields + full body replacement."""
    item = _get_story_item_or_404(arc_id)
    settings = get_settings()
    path = settings.stories_path / item.relative_path
    current_meta, _current_body = frontmatter.parse_file(path)
    new_meta = replace(
        current_meta,
        name=titre,
        type=type_fiche,
        status=statut,
        scope=scope,
        related=_split_csv(related),
    )
    repository.write_node(settings.stories_path, item.relative_path, new_meta, body)
    with get_session() as session:
        reindex_one(settings.stories_path, item.relative_path, item.saga, item.tome, session)
    return RedirectResponse(url=f'/stories/arcs/{arc_id}', status_code=303)


@router.get('/tomes/{tome_id}', response_class=HTMLResponse)
def tome_detail(request: Request, tome_id: str) -> HTMLResponse:
    """Tome detail: its acts, plus a form to create a new one."""
    item = _get_story_item_or_404(tome_id)
    settings = get_settings()
    tome_path = (settings.stories_path / item.relative_path).parent
    acts = _list_dir_nodes(tome_path, is_act_folder)
    return templates.TemplateResponse(request, 'stories/tome.html', {'tome': item, 'actes': acts})


@router.post('/tomes/{tome_id}/actes')
def create_act_under_tome(
    tome_id: str,
    slug: Annotated[str, Form()],
    numero: Annotated[int, Form()],
    titre: Annotated[str, Form()],
    fonction_narrative: Annotated[str, Form()] = '',
) -> RedirectResponse:
    """Create a new act under a tome."""
    item = _get_story_item_or_404(tome_id)
    settings = get_settings()
    tome_path = (settings.stories_path / item.relative_path).parent
    _create_act(settings, tome_path, item.saga, item.tome, slug, numero, titre, fonction_narrative)
    return RedirectResponse(url=f'/stories/tomes/{tome_id}', status_code=303)


@router.get('/actes/{act_id}', response_class=HTMLResponse)
def act_detail(request: Request, act_id: str) -> HTMLResponse:
    """Act detail: its chapters, plus a form to create a new one."""
    item = _get_story_item_or_404(act_id)
    settings = get_settings()
    act_path = (settings.stories_path / item.relative_path).parent
    chapitres = _list_chapters(act_path)
    return templates.TemplateResponse(
        request,
        'stories/acte.html',
        {'acte': item, 'chapitres': chapitres},
    )


@router.post('/actes/{act_id}/chapters')
def create_chapter(
    act_id: str,
    slug: Annotated[str, Form()],
    numero: Annotated[int, Form()],
    titre: Annotated[str, Form()],
    etat_initial_protagoniste: Annotated[str, Form()] = '',
    etat_final_protagoniste: Annotated[str, Form()] = '',
    related: Annotated[str, Form()] = '',
) -> RedirectResponse:
    """Create a new (empty) chapter under an act."""
    item = _get_story_item_or_404(act_id)
    settings = get_settings()
    act_path = (settings.stories_path / item.relative_path).parent
    chapter_path = act_path / CHAPTER_DIRNAME / f'{slug}.md'
    if chapter_path.exists():
        raise HTTPException(status_code=409, detail=f'{slug} already exists')
    meta = StoryFrontmatter(
        id=slug,
        type='chapitre',
        name=titre,
        numero=numero,
        etat_initial_protagoniste=etat_initial_protagoniste,
        etat_final_protagoniste=etat_final_protagoniste,
        related=_split_csv(related),
    )
    relative = chapter_path.relative_to(settings.stories_path)
    repository.write_node(settings.stories_path, str(relative), meta, '')
    with get_session() as session:
        reindex_one(settings.stories_path, str(relative), item.saga, item.tome, session)
    return RedirectResponse(url=f'/stories/chapters/{meta.id}', status_code=303)


@router.get('/chapters/{chapter_id}', response_class=HTMLResponse)
def chapter_detail(request: Request, chapter_id: str) -> HTMLResponse:
    """Chapter detail: rendered body."""
    item = _get_story_item_or_404(chapter_id)
    settings = get_settings()
    _, body = frontmatter.parse_file(settings.stories_path / item.relative_path)
    return templates.TemplateResponse(
        request,
        'stories/chapitre.html',
        {'chapitre': item, 'body': body},
    )


@router.get('/chapters/{chapter_id}/edit', response_class=HTMLResponse)
def chapter_edit_form(request: Request, chapter_id: str) -> HTMLResponse:
    """Whole-chapter edit form: planning fields + body."""
    item = _get_story_item_or_404(chapter_id)
    settings = get_settings()
    meta, body = frontmatter.parse_file(settings.stories_path / item.relative_path)
    return templates.TemplateResponse(
        request,
        'stories/chapitre_edit.html',
        {'chapitre': item, 'meta': meta, 'body': body, 'related_text': ', '.join(meta.related)},
    )


@router.post('/chapters/{chapter_id}/edit')
def chapter_edit_submit(
    chapter_id: str,
    titre: Annotated[str, Form()],
    numero: Annotated[int, Form()],
    statut: Annotated[str, Form()],
    body: Annotated[str, Form()],
    etat_initial_protagoniste: Annotated[str, Form()] = '',
    etat_final_protagoniste: Annotated[str, Form()] = '',
    related: Annotated[str, Form()] = '',
) -> RedirectResponse:
    """Save a whole-chapter edit: planning fields + full body replacement."""
    item = _get_story_item_or_404(chapter_id)
    settings = get_settings()
    path = settings.stories_path / item.relative_path
    current_meta, _current_body = frontmatter.parse_file(path)
    new_meta = replace(
        current_meta,
        name=titre,
        numero=numero,
        status=statut,
        etat_initial_protagoniste=etat_initial_protagoniste,
        etat_final_protagoniste=etat_final_protagoniste,
        related=_split_csv(related),
    )
    repository.write_node(settings.stories_path, item.relative_path, new_meta, body)
    with get_session() as session:
        reindex_one(settings.stories_path, item.relative_path, item.saga, item.tome, session)
    return RedirectResponse(url=f'/stories/chapters/{chapter_id}', status_code=303)


@router.get('/chapters/{chapter_id}/redact', response_class=HTMLResponse)
def redact_form(request: Request, chapter_id: str) -> HTMLResponse:
    """Show the scene-generation form."""
    item = _get_story_item_or_404(chapter_id)
    return templates.TemplateResponse(
        request,
        'stories/redact.html',
        {'chapitre': item, 'instruction': '', 'contraintes': '', 'draft': ''},
    )


@router.post('/chapters/{chapter_id}/redact/generate', response_class=HTMLResponse)
def redact_generate(
    request: Request,
    chapter_id: str,
    instruction: Annotated[str, Form()],
    contraintes: Annotated[str, Form()] = '',
) -> HTMLResponse:
    """Assemble context, render the prompt, and generate a draft (not persisted)."""
    item = _get_story_item_or_404(chapter_id)
    settings = get_settings()
    with get_session() as session:
        ctx = compose_redaction_context(session, settings, chapter_id, instruction, contraintes)
    draft = generate_prose(render_prompt(ctx))
    return templates.TemplateResponse(
        request,
        'stories/redact.html',
        {'chapitre': item, 'instruction': instruction, 'contraintes': contraintes, 'draft': draft},
    )


@router.post('/chapters/{chapter_id}/redact/append')
def redact_append(chapter_id: str, draft: Annotated[str, Form()]) -> RedirectResponse:
    """Append the (human-reviewed) draft to the chapter's body behind a `***` break."""
    item = _get_story_item_or_404(chapter_id)
    settings = get_settings()
    with get_session() as session:
        append_scene(settings, item, draft, session)
    return RedirectResponse(url=f'/stories/chapters/{chapter_id}', status_code=303)
