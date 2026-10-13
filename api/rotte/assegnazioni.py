"""Registrare chi si e' preso chi, un giocatore alla volta.

Il draft si puo' fare qui dentro (la Draft Room) oppure fuori, e il fuori
succede: una chiamata al telefono, uno scambio concordato a voce, un errore
da correggere. Questa pagina serve a quello — **registrare**, non a condurre.

Per questo la rosa che sfora non ferma l'assegnazione: avvisa. Chi la usa sta
scrivendo quel che e' successo davvero, e un sito che si rifiuta di prendere
nota della realta' costringe a tenerne una copia da un'altra parte. Le
violazioni si vedono prima di premere, e restano scritte nel cruscotto finche'
qualcuno non le sistema.

Le cose che invece **non si registrano** sono quelle che non vogliono dire
niente: un giocatore che e' gia' di un'altra squadra, un contratto di zero
anni, una squadra che non esiste.
"""

from __future__ import annotations

from fastapi import APIRouter, HTTPException, status
from pydantic import BaseModel, Field

from fantacalcio.conformita import Momento, verifica_rosa
from fantacalcio.data import (
    assegna_contratto,
    carica_giocatori,
    carica_rose,
    svincolati,
)

from ..contesto import DATA_DRAFT, Contesto, contesto_di
from ..dipendenze import UtenteDentro

rotte = APIRouter(tags=["assegnazioni"])

NON_ELABORABILE = 422


class LiberoLetto(BaseModel):
    id: int
    nome: str
    club: str
    ruoli: list[str]
    ingaggio: float
    nazionalita: str
    u21: bool


class SquadraLetta(BaseModel):
    id: int
    nome: str
    giocatori: int
    anni_impegnati: int
    monte_ingaggi: float
    # Quanto resta sotto il tetto: e' il numero che decide se un'assegnazione
    # e' tranquilla o no, e il browser non deve ricavarselo da solo.
    spazio_salariale: float


class PaginaAssegnazioni(BaseModel):
    posso_assegnare: bool
    anni_minimo: int
    anni_massimo: int
    monte_anni: int
    limite_cap: float
    in_listone: int
    liberi: list[LiberoLetto]
    squadre: list[SquadraLetta]


class ViolazioneLetta(BaseModel):
    codice: str
    articolo: str
    messaggio: str
    bloccante: bool


class DaAssegnare(BaseModel):
    giocatore_id: int
    squadra_id: int
    anni: int = Field(ge=1)


class EsitoAssegnazione(BaseModel):
    fatta: bool
    messaggio: str
    # Com'e' messa la rosa **dopo**: avvisi, non rifiuti.
    violazioni: list[ViolazioneLetta]


def _solo_chi_importa(utente) -> Contesto:
    if not utente.puo_importare:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Le assegnazioni le registra il presidente di lega (art. 1).",
        )
    return contesto_di(utente)


def _controlla(ctx: Contesto, richiesta: DaAssegnare):
    """Quel che non si registra proprio, perche' non vuol dire niente."""
    giocatori = carica_giocatori(ctx.arch)
    chi = giocatori.get(richiesta.giocatore_id)
    if chi is None:
        raise HTTPException(
            status_code=NON_ELABORABILE, detail="Quel giocatore non esiste."
        )

    rose = carica_rose(ctx.arch)
    rosa = rose.get(richiesta.squadra_id)
    if rosa is None:
        raise HTTPException(
            status_code=NON_ELABORABILE, detail="Quella squadra non esiste."
        )

    if chi.id not in svincolati(ctx.arch, giocatori):
        proprietaria = next(
            (
                r.squadra.nome
                for r in rose.values()
                if any(c.giocatore_id == chi.id for c in r.contratti)
            ),
            "un'altra squadra",
        )
        raise HTTPException(
            status_code=NON_ELABORABILE,
            detail=(
                f"{chi.nome} e' gia' di {proprietaria}: prima va svincolato o "
                f"scambiato. Un giocatore sta in una rosa sola."
            ),
        )

    minimo = ctx.parametri.contratto_anni_minimo
    massimo = ctx.parametri.contratto_anni_massimo
    if not minimo <= richiesta.anni <= massimo:
        raise HTTPException(
            status_code=NON_ELABORABILE,
            detail=(
                f"Contratto di {richiesta.anni} anni: ammessi da {minimo} a {massimo}."
            ),
        )
    return chi, rosa


def _violazioni(ctx: Contesto, rosa, chi, anni: int) -> list[ViolazioneLetta]:
    """Come sarebbe la rosa con dentro questo contratto.

    Si guarda con `Momento.DRAFT`, lo stesso della Draft Room: i tetti
    contano, i minimi no. Una rosa a meta' costruzione e' corta per
    definizione, e dirlo a ogni assegnazione sarebbe rumore.
    """
    futura = rosa.con_giocatore(chi, anni)
    stato = verifica_rosa(futura, DATA_DRAFT, ctx.parametri, Momento.DRAFT)
    return [
        ViolazioneLetta(
            codice=v.codice,
            articolo=v.articolo,
            messaggio=v.messaggio,
            bloccante=v.bloccante,
        )
        for v in stato.violazioni
    ]


@rotte.get("/assegnazioni", response_model=PaginaAssegnazioni)
def pagina(utente: UtenteDentro) -> PaginaAssegnazioni:
    """Chi c'e' da assegnare e a quali squadre."""
    ctx = contesto_di(utente)
    giocatori = carica_giocatori(ctx.arch)
    liberi = svincolati(ctx.arch, giocatori)
    rose = carica_rose(ctx.arch)

    return PaginaAssegnazioni(
        posso_assegnare=utente.puo_importare,
        anni_minimo=ctx.parametri.contratto_anni_minimo,
        anni_massimo=ctx.parametri.contratto_anni_massimo,
        monte_anni=ctx.parametri.monte_anni,
        limite_cap=ctx.parametri.salary_cap,
        in_listone=len(giocatori),
        liberi=sorted(
            (
                LiberoLetto(
                    id=g.id,
                    nome=g.nome,
                    club=g.club,
                    ruoli=list(g.ruoli),
                    ingaggio=g.ingaggio,
                    nazionalita=g.nazionalita,
                    u21=g.under_21(ctx.riferimento_u21, ctx.parametri),
                )
                for gid, g in giocatori.items()
                if gid in liberi
            ),
            key=lambda g: -g.ingaggio,
        ),
        squadre=[
            SquadraLetta(
                id=id_,
                nome=rosa.squadra.nome,
                giocatori=rosa.dimensione,
                anni_impegnati=rosa.anni_impegnati,
                monte_ingaggi=rosa.monte_ingaggi,
                spazio_salariale=ctx.parametri.salary_cap - rosa.spesa_salariale,
            )
            for id_, rosa in sorted(rose.items(), key=lambda v: v[1].squadra.nome.lower())
        ],
    )


@rotte.post("/assegnazioni/anteprima", response_model=EsitoAssegnazione)
def anteprima(richiesta: DaAssegnare, utente: UtenteDentro) -> EsitoAssegnazione:
    """Cosa succederebbe alla rosa, senza scrivere niente."""
    ctx = _solo_chi_importa(utente)
    chi, rosa = _controlla(ctx, richiesta)
    return EsitoAssegnazione(
        fatta=False,
        messaggio="",
        violazioni=_violazioni(ctx, rosa, chi, richiesta.anni),
    )


@rotte.post("/assegnazioni", response_model=EsitoAssegnazione)
def assegna(richiesta: DaAssegnare, utente: UtenteDentro) -> EsitoAssegnazione:
    """Registra il contratto. Una rosa che sfora avvisa, non ferma."""
    ctx = _solo_chi_importa(utente)
    chi, rosa = _controlla(ctx, richiesta)
    violazioni = _violazioni(ctx, rosa, chi, richiesta.anni)

    assegna_contratto(ctx.arch, chi.id, richiesta.squadra_id, richiesta.anni)

    anni = "anno" if richiesta.anni == 1 else "anni"
    return EsitoAssegnazione(
        fatta=True,
        messaggio=(f"{chi.nome} a {rosa.squadra.nome}, {richiesta.anni} {anni}."),
        violazioni=violazioni,
    )
