"""CRUD for the Tome → Acte → Chapitre → Partie sequencer."""

from __future__ import annotations

import json
from typing import Annotated

from fastapi import APIRouter
from fastapi import Form
from fastapi import HTTPException
from fastapi import Request
from fastapi.responses import HTMLResponse
from fastapi.responses import RedirectResponse
from sqlmodel import select

from ether.db import get_session
from ether.sequencer.models import Acte
from ether.sequencer.models import Chapitre
from ether.sequencer.models import Partie
from ether.sequencer.models import Tome
from ether.templates import templates

router = APIRouter(prefix='/sequencer')


def _split_ids(text: str) -> list[str]:
    return [part.strip() for part in text.split(',') if part.strip()]


@router.get('', response_class=HTMLResponse)
def sequencer_index(request: Request) -> HTMLResponse:
    """List every tome."""
    with get_session() as session:
        query = select(Tome).order_by(Tome.numero)  # type: ignore[arg-type]  # ty:ignore[invalid-argument-type]
        tomes = list(session.exec(query))
    return templates.TemplateResponse(request, 'sequencer/index.html', {'tomes': tomes})


@router.post('/tomes')
def create_tome(
    numero: Annotated[int, Form()],
    titre: Annotated[str, Form()],
    theme_specifique: Annotated[str, Form()] = '',
    question_centrale: Annotated[str, Form()] = '',
) -> RedirectResponse:
    """Create a new tome."""
    with get_session() as session:
        tome = Tome(
            numero=numero,
            titre=titre,
            theme_specifique=theme_specifique,
            question_centrale=question_centrale,
        )
        session.add(tome)
        session.commit()
    return RedirectResponse(url='/sequencer', status_code=303)


@router.get('/tomes/{tome_id}', response_class=HTMLResponse)
def tome_detail(request: Request, tome_id: int) -> HTMLResponse:
    """Show a tome and its actes."""
    with get_session() as session:
        tome = session.get(Tome, tome_id)
        if tome is None:
            raise HTTPException(status_code=404, detail=f'Unknown tome: {tome_id}')
        query = select(Acte).where(Acte.tome_id == tome_id)
        query = query.order_by(Acte.numero)  # type: ignore[arg-type]  # ty:ignore[invalid-argument-type]
        actes = list(session.exec(query))
    return templates.TemplateResponse(
        request,
        'sequencer/tome.html',
        {'tome': tome, 'actes': actes},
    )


@router.post('/tomes/{tome_id}/actes')
def create_acte(
    tome_id: int,
    numero: Annotated[int, Form()],
    titre: Annotated[str, Form()],
    fonction_narrative: Annotated[str, Form()] = '',
) -> RedirectResponse:
    """Create a new acte within a tome."""
    with get_session() as session:
        if session.get(Tome, tome_id) is None:
            raise HTTPException(status_code=404, detail=f'Unknown tome: {tome_id}')
        acte = Acte(
            numero=numero,
            titre=titre,
            fonction_narrative=fonction_narrative,
            tome_id=tome_id,
        )
        session.add(acte)
        session.commit()
    return RedirectResponse(url=f'/sequencer/tomes/{tome_id}', status_code=303)


@router.get('/actes/{acte_id}', response_class=HTMLResponse)
def acte_detail(request: Request, acte_id: int) -> HTMLResponse:
    """Show an acte and its chapitres."""
    with get_session() as session:
        acte = session.get(Acte, acte_id)
        if acte is None:
            raise HTTPException(status_code=404, detail=f'Unknown acte: {acte_id}')
        query = select(Chapitre).where(Chapitre.acte_id == acte_id)
        query = query.order_by(Chapitre.numero)  # type: ignore[arg-type]  # ty:ignore[invalid-argument-type]
        chapitres = list(session.exec(query))
    return templates.TemplateResponse(
        request,
        'sequencer/acte.html',
        {'acte': acte, 'chapitres': chapitres},
    )


@router.post('/actes/{acte_id}/chapitres')
def create_chapitre(
    acte_id: int,
    numero: Annotated[int, Form()],
    titre: Annotated[str, Form()],
    objectif_narratif: Annotated[str, Form()] = '',
    etat_initial_protagoniste: Annotated[str, Form()] = '',
    etat_final_protagoniste: Annotated[str, Form()] = '',
) -> RedirectResponse:
    """Create a new chapitre within an acte."""
    with get_session() as session:
        if session.get(Acte, acte_id) is None:
            raise HTTPException(status_code=404, detail=f'Unknown acte: {acte_id}')
        chapitre = Chapitre(
            numero=numero,
            titre=titre,
            objectif_narratif=objectif_narratif,
            etat_initial_protagoniste=etat_initial_protagoniste,
            etat_final_protagoniste=etat_final_protagoniste,
            acte_id=acte_id,
        )
        session.add(chapitre)
        session.commit()
    return RedirectResponse(url=f'/sequencer/actes/{acte_id}', status_code=303)


@router.get('/chapitres/{chapitre_id}', response_class=HTMLResponse)
def chapitre_detail(request: Request, chapitre_id: int) -> HTMLResponse:
    """Show a chapitre, its linked fiches, and its parties (scenes)."""
    with get_session() as session:
        chapitre = session.get(Chapitre, chapitre_id)
        if chapitre is None:
            raise HTTPException(status_code=404, detail=f'Unknown chapitre: {chapitre_id}')
        query = select(Partie).where(Partie.chapitre_id == chapitre_id)
        query = query.order_by(Partie.numero)  # type: ignore[arg-type]  # ty:ignore[invalid-argument-type]
        parties = list(session.exec(query))
    return templates.TemplateResponse(
        request,
        'sequencer/chapitre.html',
        {
            'chapitre': chapitre,
            'parties': parties,
            'fiches_liees_text': ', '.join(json.loads(chapitre.fiches_liees_json or '[]')),
        },
    )


@router.post('/chapitres/{chapitre_id}/fiches-liees')
def update_fiches_liees(
    chapitre_id: int,
    fiches_liees: Annotated[str, Form()] = '',
) -> RedirectResponse:
    """Update the fiches (characters, places, arcs...) relevant to this chapitre."""
    with get_session() as session:
        chapitre = session.get(Chapitre, chapitre_id)
        if chapitre is None:
            raise HTTPException(status_code=404, detail=f'Unknown chapitre: {chapitre_id}')
        chapitre.fiches_liees_json = json.dumps(_split_ids(fiches_liees), ensure_ascii=False)
        session.add(chapitre)
        session.commit()
    return RedirectResponse(url=f'/sequencer/chapitres/{chapitre_id}', status_code=303)


@router.post('/chapitres/{chapitre_id}/parties')
def create_partie(
    chapitre_id: int,
    numero: Annotated[int, Form()],
    objectif: Annotated[str, Form()] = '',
    evenement_cle: Annotated[str, Form()] = '',
    impact_sur_protagoniste: Annotated[str, Form()] = '',
) -> RedirectResponse:
    """Create a new partie (scene) within a chapitre."""
    with get_session() as session:
        if session.get(Chapitre, chapitre_id) is None:
            raise HTTPException(status_code=404, detail=f'Unknown chapitre: {chapitre_id}')
        partie = Partie(
            numero=numero,
            objectif=objectif,
            evenement_cle=evenement_cle,
            impact_sur_protagoniste=impact_sur_protagoniste,
            chapitre_id=chapitre_id,
        )
        session.add(partie)
        session.commit()
    return RedirectResponse(url=f'/sequencer/chapitres/{chapitre_id}', status_code=303)
