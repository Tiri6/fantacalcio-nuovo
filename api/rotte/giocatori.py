"""Il listone: tutti i giocatori, con chi li possiede.

Si manda **tutto in una volta** invece di filtrare lato server. Sono
cinquecento righe, e filtrarle nel browser vuol dire che scrivere nella
casella di ricerca non fa partire una richiesta a ogni lettera: e' la
reattivita' che Streamlit non poteva dare, ed e' il motivo per cui si rifa
il sito.
"""

from __future__ import annotations

from fastapi import APIRouter
from pydantic import BaseModel

from fantacalcio.data import carica_rose
from fantacalcio.vista import SVINCOLATO, elenco_giocatori

from ..contesto import contesto_di
from ..dipendenze import UtenteDentro

rotte = APIRouter(tags=["giocatori"])


class Giocatore(BaseModel):
    id: int
    nome: str
    club: str
    ruoli: list[str]
    ruolo_classic: str
    squadra: str
    anni: int
    ingaggio: float
    nazionalita: str
    data_nascita: str | None
    eta: int | None
    italiano: bool
    u21: bool
    quotazione: float | None
    fvm: float | None


class Listone(BaseModel):
    giocatori: list[Giocatore]
    svincolato: str
    # Quanti hanno il dato: la pagina lo dice in testa, perche' finche'
    # mancano stipendi e date di nascita meta' dei conti non si possono fare.
    con_stipendio: int
    con_data_nascita: int
    riferimento_u21: str


@rotte.get("/giocatori", response_model=Listone)
def listone(utente: UtenteDentro) -> Listone:
    ctx = contesto_di(utente)
    nomi = {id_: rosa.squadra.nome for id_, rosa in carica_rose(ctx.arch).items()}

    righe = elenco_giocatori(ctx.arch, ctx.riferimento_u21, ctx.parametri, nomi)

    return Listone(
        giocatori=[Giocatore(**r) for r in righe],
        svincolato=SVINCOLATO,
        con_stipendio=sum(1 for r in righe if r["ingaggio"]),
        con_data_nascita=sum(1 for r in righe if r["data_nascita"]),
        riferimento_u21=ctx.riferimento_u21.isoformat(),
    )
