"""Scene generation: build context → render prompt → generate → review → validate.

Mirrors `studio-conception-narrative`'s flow: generation never persists
anything by itself — only `POST /redaction/{partie_id}/valider` writes
`Partie.contenu_genere`.
"""

from __future__ import annotations

from typing import Annotated

from fastapi import APIRouter
from fastapi import Form
from fastapi import HTTPException
from fastapi import Request
from fastapi.responses import HTMLResponse
from fastapi.responses import RedirectResponse

from ether.config import get_settings
from ether.db import get_session
from ether.sequencer.models import Partie
from ether.sequencer.redaction import compose_redaction_context
from ether.sequencer.redaction import generate_prose
from ether.sequencer.redaction import render_prompt
from ether.templates import templates

router = APIRouter(prefix='/redaction')


def _get_partie_or_404(partie_id: int) -> Partie:
    with get_session() as session:
        partie = session.get(Partie, partie_id)
    if partie is None:
        raise HTTPException(status_code=404, detail=f'Unknown partie: {partie_id}')
    return partie


@router.get('/{partie_id}', response_class=HTMLResponse)
def redaction_form(request: Request, partie_id: int) -> HTMLResponse:
    """Show the scene generation form."""
    partie = _get_partie_or_404(partie_id)
    return templates.TemplateResponse(
        request,
        'redaction/index.html',
        {'partie': partie, 'instruction': '', 'contraintes': '', 'draft': ''},
    )


@router.post('/{partie_id}/generer', response_class=HTMLResponse)
def redaction_generer(
    request: Request,
    partie_id: int,
    instruction: Annotated[str, Form()],
    contraintes: Annotated[str, Form()] = '',
) -> HTMLResponse:
    """Assemble context, render the prompt, and generate a draft (not persisted)."""
    partie = _get_partie_or_404(partie_id)
    settings = get_settings()

    with get_session() as session:
        ctx = compose_redaction_context(
            session,
            settings,
            chapitre_id=partie.chapitre_id,
            partie_id=partie.id,
            instruction=instruction,
            contraintes=contraintes,
        )
    prompt = render_prompt(ctx)
    draft = generate_prose(prompt)

    return templates.TemplateResponse(
        request,
        'redaction/index.html',
        {'partie': partie, 'instruction': instruction, 'contraintes': contraintes, 'draft': draft},
    )


@router.post('/{partie_id}/valider')
def redaction_valider(partie_id: int, draft: Annotated[str, Form()]) -> RedirectResponse:
    """Persist the (human-reviewed) draft as the scene's validated prose."""
    with get_session() as session:
        partie = session.get(Partie, partie_id)
        if partie is None:
            raise HTTPException(status_code=404, detail=f'Unknown partie: {partie_id}')
        partie.contenu_genere = draft
        partie.statut = 'Validé'
        session.add(partie)
        session.commit()
        chapitre_id = partie.chapitre_id

    return RedirectResponse(url=f'/sequencer/chapitres/{chapitre_id}', status_code=303)
