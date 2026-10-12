"""Scambi fra fantallenatori: proporre, accettare, rifiutare, ratificare.

Il ciclo di vita sta tutto in `fantacalcio/scambi.py` e le regole in
`mercato.valida_scambio`: qui non si decide niente, si chiede al dominio e si
riporta. Anche i permessi — chi puo' proporre, chi puo' accettare, chi puo'
ratificare — li solleva il dominio con `TransizioneNonAmmessa`, perche'
nascondere un bottone non e' un controllo.

Lo scambio si propone **anche quando non e' valido**: la risposta porta le
violazioni insieme alla proposta, cosi' chi l'ha composta vede *cosa* non va
invece di perdere quello che aveva scritto. A fermarlo e' la ratifica.
"""

from __future__ import annotations

from datetime import datetime

from fastapi import APIRouter, HTTPException, status
from pydantic import BaseModel, Field

from fantacalcio.data import carica_rose, prossimo_id
from fantacalcio.mercato import PropostaScambio, stato_mercato
from fantacalcio.scambi import (
    Scambio,
    StatoScambio,
    TransizioneNonAmmessa,
    accetta,
    annulla,
    applica_alle_rose,
    carica_scambi,
    conta_conclusi,
    proponi,
    ratifica,
    rifiuta,
    salva_scambio,
    scambi_residui,
)

from ..contesto import contesto_di
from ..dipendenze import UtenteDentro

rotte = APIRouter(tags=["scambi"])

NON_ELABORABILE = 422


class MovimentoLetto(BaseModel):
    giocatore_id: int
    nome_giocatore: str
    da_squadra_id: int
    da_squadra: str
    a_squadra_id: int
    a_squadra: str
    anni: int


class ViolazioneLetta(BaseModel):
    codice: str
    articolo: str
    messaggio: str
    bloccante: bool


class ScambioLetto(BaseModel):
    id: int
    stato: str
    stato_etichetta: str
    aperto: bool
    squadra_a_id: int
    squadra_a: str
    squadra_b_id: int
    squadra_b: str
    movimenti: list[MovimentoLetto]
    note: str
    creato_il: str
    giornata_efficacia: int | None
    # Cosa puo' fare **chi sta guardando**, deciso dal dominio e non dedotto
    # dal front-end: se la regola cambia, cambia in un posto solo.
    posso_accettare: bool
    posso_rifiutare: bool
    posso_annullare: bool
    posso_ratificare: bool
    # Rivalidate adesso: fra la proposta e oggi le rose possono essere
    # cambiate, e uno scambio valido ieri puo' non esserlo piu'.
    violazioni: list[ViolazioneLetta]


class PaginaScambi(BaseModel):
    scambi: list[ScambioLetto]
    mia_squadra_id: int | None
    conclusi: int
    residui: int | None
    mercato_aperto: bool
    finestra: str
    squadre: list[dict]


def _nomi(ctx) -> dict[int, str]:
    return {id_: rosa.squadra.nome for id_, rosa in carica_rose(ctx.arch).items()}


def _violazioni_di(ctx, scambio: Scambio) -> list[ViolazioneLetta]:
    """Rivalida lo scambio sulle rose di adesso."""
    from fantacalcio.mercato import valida_scambio

    rose = carica_rose(ctx.arch)
    a, b = rose.get(scambio.squadra_a_id), rose.get(scambio.squadra_b_id)
    if a is None or b is None:
        return []
    trovate = valida_scambio(a, b, scambio.a_proposta(), ctx.stagione, ctx.parametri)
    return [
        ViolazioneLetta(
            codice=v.codice,
            articolo=v.articolo,
            messaggio=v.messaggio,
            bloccante=v.bloccante,
        )
        for v in trovate
    ]


def _leggi(ctx, scambio: Scambio, utente, nomi: dict[int, str]) -> ScambioLetto:
    violazioni = _violazioni_di(ctx, scambio)
    blocca = any(v.bloccante for v in violazioni)
    proposto = scambio.stato is StatoScambio.PROPOSTO
    accettato = scambio.stato is StatoScambio.ACCETTATO
    riceve = utente.e_presidente or utente.puo_gestire(scambio.squadra_b_id)
    propone = utente.e_presidente or utente.puo_gestire(scambio.squadra_a_id)

    return ScambioLetto(
        id=scambio.id,
        stato=scambio.stato.name,
        stato_etichetta=scambio.stato.etichetta,
        aperto=scambio.stato.aperto,
        squadra_a_id=scambio.squadra_a_id,
        squadra_a=nomi.get(scambio.squadra_a_id, "?"),
        squadra_b_id=scambio.squadra_b_id,
        squadra_b=nomi.get(scambio.squadra_b_id, "?"),
        movimenti=[
            MovimentoLetto(
                giocatore_id=m.giocatore_id,
                nome_giocatore=m.nome_giocatore,
                da_squadra_id=m.da_squadra_id,
                da_squadra=nomi.get(m.da_squadra_id, "?"),
                a_squadra_id=m.a_squadra_id,
                a_squadra=nomi.get(m.a_squadra_id, "?"),
                anni=m.anni_dopo,
            )
            for m in scambio.movimenti
        ],
        note=scambio.note,
        creato_il=scambio.creato_il.strftime("%d/%m/%Y %H:%M"),
        giornata_efficacia=scambio.giornata_efficacia,
        posso_accettare=proposto and riceve,
        posso_rifiutare=proposto and riceve,
        posso_annullare=scambio.stato.aperto and propone,
        # Il presidente ratifica, ma non uno scambio che non passa i controlli:
        # dirlo prima evita un bottone che risponde sempre di no.
        posso_ratificare=accettato and utente.puo_importare and not blocca,
        violazioni=violazioni,
    )


@rotte.get("/scambi", response_model=PaginaScambi)
def elenco(utente: UtenteDentro) -> PaginaScambi:
    ctx = contesto_di(utente)
    nomi = _nomi(ctx)
    registro = carica_scambi(ctx.arch)

    opzioni = ctx.lega.opzioni if ctx.lega else None
    per_stagione = opzioni.scambi_per_stagione if opzioni else 0
    mercato = stato_mercato(giornate_disputate(ctx), ctx.calendario)

    return PaginaScambi(
        scambi=[_leggi(ctx, s, utente, nomi) for s in registro],
        mia_squadra_id=utente.squadra_id,
        conclusi=(
            conta_conclusi(registro, utente.squadra_id, ctx.stagione)
            if utente.squadra_id
            else 0
        ),
        residui=(
            scambi_residui(registro, utente.squadra_id, per_stagione, ctx.stagione)
            if utente.squadra_id
            else None
        ),
        mercato_aperto=not mercato.trade_deadline_superata,
        finestra=(
            mercato.finestra_piu_recente.value if mercato.finestra_piu_recente else ""
        ),
        squadre=[{"id": id_, "nome": nome} for id_, nome in sorted(nomi.items())],
    )


def giornate_disputate(ctx) -> int:
    """Quante giornate sono gia' state giocate, per sapere che finestra e'."""
    calendario = ctx.arch.calendario()
    if calendario.empty or "gol_casa" not in calendario.columns:
        return 0
    giocate = calendario[calendario["gol_casa"].notna()]
    return int(giocate["giornata"].max()) if not giocate.empty else 0


class Proposta(BaseModel):
    squadra_b_id: int
    da_me: list[int] = Field(default_factory=list)
    da_loro: list[int] = Field(default_factory=list)
    note: str = Field(default="", max_length=500)


class EsitoProposta(BaseModel):
    scambio: ScambioLetto | None
    violazioni: list[ViolazioneLetta]
    inviata: bool


@rotte.post("/scambi", response_model=EsitoProposta)
def proponi_scambio(richiesta: Proposta, utente: UtenteDentro) -> EsitoProposta:
    """Propone uno scambio. Con violazioni bloccanti non si invia."""
    ctx = contesto_di(utente)
    rose = carica_rose(ctx.arch)

    if utente.squadra_id is None:
        raise HTTPException(
            status_code=NON_ELABORABILE,
            detail="Senza una squadra non si propongono scambi.",
        )
    mia = rose.get(utente.squadra_id)
    altra = rose.get(richiesta.squadra_b_id)
    if mia is None or altra is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND, detail="Squadra inesistente."
        )
    if mia.squadra.id == altra.squadra.id:
        raise HTTPException(
            status_code=NON_ELABORABILE,
            detail="Uno scambio con se stessi non muove niente.",
        )

    proposta = PropostaScambio(
        da_squadra_a=tuple(richiesta.da_me),
        da_squadra_b=tuple(richiesta.da_loro),
    )

    try:
        scambio, violazioni = proponi(
            prossimo_id(ctx.arch, "scambi"),
            mia,
            altra,
            proposta,
            utente,
            ctx.stagione,
            note=richiesta.note,
            parametri=ctx.parametri,
        )
    except TransizioneNonAmmessa as errore:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN, detail=str(errore)
        ) from errore
    except (ValueError, KeyError) as errore:
        raise HTTPException(status_code=NON_ELABORABILE, detail=str(errore)) from errore

    lette = [
        ViolazioneLetta(
            codice=v.codice,
            articolo=v.articolo,
            messaggio=v.messaggio,
            bloccante=v.bloccante,
        )
        for v in violazioni
    ]
    if any(v.bloccante for v in lette):
        # Non si salva, ma si restituisce tutto: chi ha composto la proposta
        # deve vedere cosa non va senza ricominciare da capo.
        return EsitoProposta(scambio=None, violazioni=lette, inviata=False)

    salva_scambio(ctx.arch, scambio)
    return EsitoProposta(
        scambio=_leggi(ctx, scambio, utente, _nomi(ctx)),
        violazioni=lette,
        inviata=True,
    )


def _trova(ctx, scambio_id: int) -> Scambio:
    for scambio in carica_scambi(ctx.arch):
        if scambio.id == scambio_id:
            return scambio
    raise HTTPException(
        status_code=status.HTTP_404_NOT_FOUND, detail="Scambio inesistente."
    )


class Decisione(BaseModel):
    azione: str  # "accetta" | "rifiuta" | "annulla" | "ratifica"
    giornata_efficacia: int | None = None


@rotte.post("/scambi/{scambio_id}", response_model=ScambioLetto)
def decidi(scambio_id: int, richiesta: Decisione, utente: UtenteDentro) -> ScambioLetto:
    """Accetta, rifiuta, ritira o ratifica. Il dominio dice chi puo' cosa."""
    ctx = contesto_di(utente)
    scambio = _trova(ctx, scambio_id)
    adesso = datetime.now()

    try:
        if richiesta.azione == "accetta":
            aggiornato = accetta(scambio, utente, adesso)
        elif richiesta.azione == "rifiuta":
            aggiornato = rifiuta(scambio, utente, adesso)
        elif richiesta.azione == "annulla":
            aggiornato = annulla(scambio, utente, adesso)
        elif richiesta.azione == "ratifica":
            rose = carica_rose(ctx.arch)
            a, b = rose.get(scambio.squadra_a_id), rose.get(scambio.squadra_b_id)
            if a is None or b is None:
                raise HTTPException(
                    status_code=status.HTTP_404_NOT_FOUND,
                    detail="Una delle due squadre non esiste piu'.",
                )
            aggiornato, nuova_a, nuova_b = ratifica(
                scambio,
                a,
                b,
                utente,
                ctx.stagione,
                giornata_efficacia=richiesta.giornata_efficacia,
                quando=adesso,
                parametri=ctx.parametri,
            )
            # Le rose si scrivono **prima** dello scambio: se la seconda
            # scrittura fallisce resta uno scambio accettato su rose gia'
            # spostate — si vede e si ratifica di nuovo. Al contrario sarebbe
            # uno scambio ratificato che non ha mosso nessuno.
            applica_alle_rose(ctx.arch, nuova_a, nuova_b)
        else:
            raise HTTPException(
                status_code=NON_ELABORABILE,
                detail=f"Azione sconosciuta: {richiesta.azione}",
            )
    except TransizioneNonAmmessa as errore:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN, detail=str(errore)
        ) from errore

    salva_scambio(ctx.arch, aggiornato)
    return _leggi(ctx, aggiornato, utente, _nomi(ctx))
