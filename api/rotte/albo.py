"""Albo d'oro: chi ha vinto cosa, stagione per stagione.

Una competizione ha **un** vincitore per stagione: registrare lo stesso
titolo due volte non aggiunge una riga, sostituisce quella che c'era. La
regola sta nel dominio (`competizioni.titolo_esistente`), qui si usa.

Le competizioni che si possono premiare sono quelle che la lega gioca
davvero: un albo che offre la F1 Rush a una lega che non la disputa
racconta una storia che non e' successa.
"""

from __future__ import annotations

from fastapi import APIRouter, HTTPException, status
from pydantic import BaseModel, Field

from fantacalcio.competizioni import (
    CompetizioneNonValida,
    TipoCompetizione,
    Titolo,
    bacheca_squadre,
    crea_titolo,
    ordina_albo,
    titolo_esistente,
)
from fantacalcio.data import (
    carica_albo,
    carica_rose,
    elimina_titolo,
    prossimo_id,
    salva_titolo,
)

from ..contesto import contesto_di
from ..dipendenze import UtenteDentro

rotte = APIRouter(tags=["albo"])

NON_ELABORABILE = 422


class TitoloLetto(BaseModel):
    id: int
    competizione: str
    competizione_etichetta: str
    competizione_icona: str
    stagione: str
    squadra_nome: str
    squadra_id: int | None
    note: str


class BachecaSquadra(BaseModel):
    """Quante ne ha vinte una squadra, per competizione."""

    squadra: str
    titoli: dict[str, int]
    totale: int


class Albo(BaseModel):
    titoli: list[TitoloLetto]
    bacheche: list[BachecaSquadra]
    # Solo le competizioni che la lega gioca davvero.
    competizioni: list[dict[str, str]]
    squadre: list[str]
    stagione_corrente: str
    nome_lega: str
    posso_registrare: bool


class Registrazione(BaseModel):
    competizione: str
    stagione: str = Field(min_length=1, max_length=20)
    squadra_nome: str = Field(min_length=1, max_length=60)
    note: str = Field(default="", max_length=200)


def _letto(titolo: Titolo) -> TitoloLetto:
    return TitoloLetto(
        id=titolo.id,
        competizione=titolo.competizione.name,
        competizione_etichetta=titolo.competizione.etichetta,
        competizione_icona=titolo.competizione.icona,
        stagione=titolo.stagione,
        squadra_nome=titolo.squadra_nome,
        squadra_id=titolo.squadra_id,
        note=titolo.note,
    )


def _amministra(utente, lega) -> bool:
    """Chi ha creato la lega, oppure il presidente.

    Stessa regola della bacheca, e sta qui per lo stesso motivo: nascondere
    il modulo non e' un controllo.
    """
    admin = getattr(lega, "admin_id", None)
    if lega is not None and getattr(utente, "id", None) == admin:
        return True
    return bool(utente.puo_importare)


def _albo(utente) -> Albo:
    ctx = contesto_di(utente)
    lega_id = ctx.lega.id if ctx.lega else None
    titoli = ordina_albo(carica_albo(ctx.arch, lega_id))

    conteggi = bacheca_squadre(titoli)
    bacheche = [
        BachecaSquadra(
            squadra=squadra,
            titoli={c.name: quanti for c, quanti in per_competizione.items()},
            totale=sum(per_competizione.values()),
        )
        for squadra, per_competizione in conteggi.items()
    ]
    # Prima chi ha vinto di piu'; a pari merito, in ordine alfabetico.
    bacheche.sort(key=lambda b: (-b.totale, b.squadra))

    attive = ctx.lega.opzioni.competizioni if ctx.lega else [TipoCompetizione.CAMPIONATO]
    rose = carica_rose(ctx.arch)
    nomi = sorted(
        r.squadra.nome
        for r in rose.values()
        if ctx.lega is None or r.squadra.lega_id in (None, ctx.lega.id)
    )

    return Albo(
        titoli=[_letto(t) for t in titoli],
        bacheche=bacheche,
        competizioni=[
            {"nome": c.name, "etichetta": c.etichetta, "icona": c.icona} for c in attive
        ],
        squadre=nomi,
        stagione_corrente=ctx.stagione,
        nome_lega=ctx.lega.nome if ctx.lega else "",
        posso_registrare=_amministra(utente, ctx.lega),
    )


@rotte.get("/albo", response_model=Albo)
def albo(utente: UtenteDentro) -> Albo:
    return _albo(utente)


@rotte.post("/albo", response_model=TitoloLetto, status_code=status.HTTP_201_CREATED)
def registra(richiesta: Registrazione, utente: UtenteDentro) -> TitoloLetto:
    ctx = contesto_di(utente)
    if ctx.lega is None:
        raise HTTPException(
            status_code=NON_ELABORABILE,
            detail="Un titolo appartiene a una lega, e tu non ne hai una.",
        )
    if not _amministra(utente, ctx.lega):
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Solo chi amministra la lega puo' registrare un titolo.",
        )

    try:
        competizione = TipoCompetizione[richiesta.competizione]
    except KeyError:
        raise HTTPException(
            status_code=NON_ELABORABILE,
            detail=f"Competizione sconosciuta: {richiesta.competizione}",
        ) from None

    if competizione not in ctx.lega.opzioni.competizioni:
        raise HTTPException(
            status_code=NON_ELABORABILE,
            detail=f"{competizione.etichetta} non si gioca in questa lega.",
        )

    rose = carica_rose(ctx.arch)
    squadra = next(
        (r.squadra for r in rose.values() if r.squadra.nome == richiesta.squadra_nome),
        None,
    )
    if squadra is None:
        raise HTTPException(
            status_code=NON_ELABORABILE,
            detail=f"Non esiste nessuna squadra chiamata «{richiesta.squadra_nome}».",
        )

    esistente = titolo_esistente(
        ordina_albo(carica_albo(ctx.arch, ctx.lega.id)), competizione, richiesta.stagione
    )

    try:
        nuovo = crea_titolo(
            # Il vincitore e' uno solo: se quella stagione e' gia' registrata
            # si riscrive la riga che c'era invece di affiancarne una seconda.
            id_=esistente.id if esistente else prossimo_id(ctx.arch, "albo"),
            lega_id=ctx.lega.id,
            competizione=competizione,
            stagione=richiesta.stagione,
            squadra_nome=squadra.nome,
            squadra_id=squadra.id,
            note=richiesta.note,
        )
    except CompetizioneNonValida as errore:
        raise HTTPException(status_code=NON_ELABORABILE, detail=str(errore)) from errore

    salva_titolo(ctx.arch, nuovo)
    return _letto(nuovo)


@rotte.delete("/albo/{titolo_id}", status_code=status.HTTP_204_NO_CONTENT)
def cancella(titolo_id: int, utente: UtenteDentro) -> None:
    ctx = contesto_di(utente)
    lega_id = ctx.lega.id if ctx.lega else None
    if not any(t.id == titolo_id for t in carica_albo(ctx.arch, lega_id)):
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND, detail="Titolo inesistente."
        )
    if not _amministra(utente, ctx.lega):
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Solo chi amministra la lega puo' cancellare un titolo.",
        )
    elimina_titolo(ctx.arch, titolo_id)
