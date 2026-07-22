"""Editor for a saga/one-shot's style manifest: a structured form, one field per section.

One manifest per saga/one-shot (`stories/<saga>/_manifest.md`) rather than a
single global file — see `ether.config.EtherSettings.manifest_path_for`.
"""

from __future__ import annotations

import datetime as dt
from typing import Annotated

from fastapi import APIRouter
from fastapi import Form
from fastapi import Request
from fastapi.responses import HTMLResponse
from fastapi.responses import RedirectResponse

from ether.ai.style_manifest import ManifestRule
from ether.ai.style_manifest import StyleManifestForm
from ether.ai.style_manifest import ensure_manifest
from ether.ai.style_manifest import parse_markdown
from ether.ai.style_manifest import read_manifest
from ether.ai.style_manifest import render_markdown
from ether.ai.style_manifest import write_manifest
from ether.config import get_settings
from ether.templates import templates

router = APIRouter()


def _zip_rules(labels: list[str], contents: list[str]) -> list[ManifestRule]:
    pairs = zip(labels, contents, strict=False)
    return [ManifestRule(label=label, content=content) for label, content in pairs]


@router.get('/style', response_class=HTMLResponse)
def style_index(request: Request) -> HTMLResponse:
    """List every saga/one-shot, linking to its manifest editor."""
    settings = get_settings()
    sagas: list[str] = []
    if settings.stories_path.is_dir():
        sagas = sorted(p.name for p in settings.stories_path.iterdir() if p.is_dir())
    return templates.TemplateResponse(request, 'style/index.html', {'sagas': sagas})


@router.get('/style/{saga}', response_class=HTMLResponse)
def style_form(request: Request, saga: str) -> HTMLResponse:
    """Show a saga's style manifest editor, scaffolding a default form if needed."""
    settings = get_settings()
    manifest_path = settings.manifest_path_for(saga)
    ensure_manifest(manifest_path, saga)
    form = parse_markdown(read_manifest(manifest_path), fallback_project_name=saga)
    return templates.TemplateResponse(request, 'style/edit.html', {'form': form, 'saga': saga})


@router.post('/style/{saga}')
def style_submit(
    saga: str,
    project_name: Annotated[str, Form()],
    intention_thematique: Annotated[str, Form()] = '',
    registre_ton: Annotated[str, Form()] = '',
    a_eviter: Annotated[str, Form()] = '',
    format_sortie: Annotated[str, Form()] = '',
    pov_label: Annotated[list[str], Form()] = [],  # noqa: B006 - FastAPI Form default sentinel
    pov_content: Annotated[list[str], Form()] = [],  # noqa: B006
    regle_label: Annotated[list[str], Form()] = [],  # noqa: B006
    regle_content: Annotated[list[str], Form()] = [],  # noqa: B006
) -> RedirectResponse:
    """Save the structured form, serialized back to that saga's manifest markdown file."""
    settings = get_settings()
    form = StyleManifestForm(
        project_name=project_name,
        updated=dt.date.today().isoformat(),
        intention_thematique=intention_thematique,
        point_de_vue=_zip_rules(pov_label, pov_content),
        registre_ton=registre_ton,
        regles_prose=_zip_rules(regle_label, regle_content),
        a_eviter=a_eviter,
        format_sortie=format_sortie,
    )
    write_manifest(settings.manifest_path_for(saga), render_markdown(form))
    return RedirectResponse(url=f'/style/{saga}', status_code=303)
