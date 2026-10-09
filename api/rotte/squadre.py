"""Le squadre della lega, con i conti che la pagina mostra in testa."""

from __future__ import annotations

from fastapi import APIRouter
from pydantic import BaseModel

from fantacalcio.data import archivio, carica_rose

from ..dipendenze import UtenteDentro

rotte = APIRouter(tags=["squadre"])


class Colori(BaseModel):
    primario: str
    secondario: str
    stile_maglia: str


class SquadraInElenco(BaseModel):
    id: int
    nome: str
    presidente: str
    motto: str
    stadio: str
    citta: str
    curva: str
    anno_fondazione: int | None
    colori: Colori
    logo: str | None
    # I conti: li calcola il dominio, non il front-end. React disegna numeri,
    # non li deduce — altrimenti la regola finirebbe in due posti.
    giocatori: int
    anni_impegnati: int
    monte_ingaggi: float
    dead_money: float
    # Vero per la squadra di chi sta guardando: serve ad aprire la pagina
    # sulla propria, come fa Streamlit oggi.
    e_mia: bool


@rotte.get("/squadre", response_model=list[SquadraInElenco])
def elenco(utente: UtenteDentro) -> list[SquadraInElenco]:
    rose = carica_rose(archivio())

    squadre = []
    for rosa in rose.values():
        s = rosa.squadra
        if utente.lega_id is not None and s.lega_id not in (None, utente.lega_id):
            # Chi sta in una lega vede la sua. Le squadre senza lega sono
            # quelle nate prima delle leghe multiple: restano visibili.
            continue
        i = s.identita
        squadre.append(
            SquadraInElenco(
                id=s.id,
                nome=s.nome,
                presidente=i.presidente,
                motto=i.motto,
                stadio=i.stadio,
                citta=i.citta,
                curva=i.curva,
                anno_fondazione=i.anno_fondazione,
                colori=Colori(
                    primario=i.colore_primario,
                    secondario=i.colore_secondario,
                    stile_maglia=i.stile_maglia.name,
                ),
                logo=i.logo,
                giocatori=rosa.dimensione,
                anni_impegnati=rosa.anni_impegnati,
                monte_ingaggi=rosa.monte_ingaggi,
                dead_money=rosa.dead_money_totale,
                e_mia=s.id == utente.squadra_id,
            )
        )

    squadre.sort(key=lambda s: s.nome)
    return squadre
