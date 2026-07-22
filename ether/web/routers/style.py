"""Editor for the project's style manifest: a structured form, one field per section."""

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
def style_form(request: Request) -> HTMLResponse:
    """Show the style manifest editor, scaffolding a default form if needed.

    Edits the first saga/one-shot found under `stories/` — an interim
    stand-in until a real per-saga picker exists (manifests moved from
    global to per-story; see the "explicitly out of scope" section of the
    stories-layout plan).
    """
    settings = get_settings()
    saga = settings.default_saga
    manifest_path = settings.manifest_path_for(saga)
    ensure_manifest(manifest_path, saga)
    form = parse_markdown(read_manifest(manifest_path), fallback_project_name=saga)
    return templates.TemplateResponse(request, 'style/edit.html', {'form': form})


@router.post('/style')
def style_submit(
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
    """Save the structured form, serialized back to the manifest markdown file."""
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
    write_manifest(settings.manifest_path_for(settings.default_saga), render_markdown(form))
    return RedirectResponse(url='/style', status_code=303)
