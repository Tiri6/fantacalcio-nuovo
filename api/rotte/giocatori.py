"""Il listone: tutti i giocatori, con chi li possiede.

Si manda **tutto in una volta** invece di filtrare lato server. Sono
cinquecento righe, e filtrarle nel browser vuol dire che scrivere nella
casella di ricerca non fa partire una richiesta a ogni lettera: e' la
reattivita' che Streamlit non poteva dare, ed e' il motivo per cui si rifa
il sito.
"""

from __future__ import annotations

from fastapi import APIRouter, HTTPException, status
from pydantic import BaseModel

from fantacalcio.data import carica_rose
from fantacalcio.leghe import puo_amministrare
from fantacalcio.under21 import (
    GiocatoreSconosciuto,
    StatusNonModificabile,
    cambia_status_u21,
)
from fantacalcio.vista import SVINCOLATO, elenco_giocatori

from ..contesto import contesto_di
from ..dipendenze import UtenteDentro

rotte = APIRouter(tags=["giocatori"])

NON_ELABORABILE = 422


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
    italiano: bool
    u21: bool
    quotazione: float | None
    fvm: float | None


class Listone(BaseModel):
    giocatori: list[Giocatore]
    svincolato: str
    # Quanti hanno il dato: la pagina lo dice in testa, perche' finche'
    # mancano gli stipendi meta' dei conti non si possono fare.
    con_stipendio: int
    riferimento_u21: str
    # Chi puo' segnare lo status Under 21: lo calcola il server.
    posso_modificare_u21: bool


@rotte.get("/giocatori", response_model=Listone)
def listone(utente: UtenteDentro) -> Listone:
    ctx = contesto_di(utente)
    nomi = {id_: rosa.squadra.nome for id_, rosa in carica_rose(ctx.arch).items()}

    righe = elenco_giocatori(ctx.arch, nomi)

    return Listone(
        giocatori=[Giocatore(**r) for r in righe],
        svincolato=SVINCOLATO,
        con_stipendio=sum(1 for r in righe if r["ingaggio"]),
        riferimento_u21=ctx.riferimento_u21.isoformat(),
        posso_modificare_u21=puo_amministrare(utente, ctx.lega),
    )


class StatusU21(BaseModel):
    italiano_u21: bool


@rotte.put("/giocatori/{giocatore_id}/u21", response_model=Giocatore)
def cambia_u21(
    giocatore_id: int, richiesta: StatusU21, utente: UtenteDentro
) -> Giocatore:
    """Segna o toglie lo status Under 21 italiano. Il permesso lo controlla il dominio."""
    ctx = contesto_di(utente)
    try:
        cambia_status_u21(
            ctx.arch,
            utente,
            ctx.lega,
            giocatore_id,
            richiesta.italiano_u21,
            ctx.parametri,
        )
    except StatusNonModificabile as errore:
        raise HTTPException(status.HTTP_403_FORBIDDEN, str(errore)) from errore
    except GiocatoreSconosciuto as errore:
        raise HTTPException(status.HTTP_404_NOT_FOUND, str(errore)) from errore
    except ValueError as errore:
        raise HTTPException(NON_ELABORABILE, str(errore)) from errore

    nomi = {id_: rosa.squadra.nome for id_, rosa in carica_rose(ctx.arch).items()}
    riga = next(r for r in elenco_giocatori(ctx.arch, nomi) if r["id"] == giocatore_id)
    return Giocatore(**riga)
