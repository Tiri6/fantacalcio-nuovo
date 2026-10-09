"""Campionato: classifica, calendario giornata per giornata, andamento punti.

I risultati arrivano da Leghe Fantacalcio, importati: qui non si gioca, si
legge. La classifica pero' non e' solo una tabella — e' anche l'ingresso
della Draft Lottery, e per questo porta i punti fantacalcio e non solo i
punti in classifica.

Tutto quello che c'e' qui dentro lo calcola `fantacalcio.standings` passando
da `vista.classifica`: questo strato impacchetta e basta.
"""

from __future__ import annotations

import math

import pandas as pd
from fastapi import APIRouter
from pydantic import BaseModel

from fantacalcio.data import calendario_dettagliato
from fantacalcio.vista import andamento_punti, classifica

from ..contesto import contesto_di
from ..dipendenze import UtenteDentro

rotte = APIRouter(tags=["campionato"])


def _numero(valore) -> float | None:
    """Da NaN di pandas a None, che e' quello che il JSON sa dire.

    Senza, `NaN` finirebbe nella risposta come letterale non valido e il
    front-end riceverebbe del JSON che non riesce nemmeno a leggere.
    """
    if valore is None:
        return None
    try:
        numero = float(valore)
    except (TypeError, ValueError):
        return None
    return None if math.isnan(numero) else numero


class RigaClassifica(BaseModel):
    posizione: int
    squadra: str
    giocate: int
    vinte: int
    pareggiate: int
    perse: int
    gol_fatti: int
    gol_subiti: int
    differenza_reti: int
    punti: int
    punti_fantacalcio: float


class Partita(BaseModel):
    giornata: int
    casa: str
    trasferta: str
    gol_casa: int | None
    gol_trasferta: int | None
    punti_casa: float | None
    punti_trasferta: float | None

    @property
    def giocata(self) -> bool:
        return self.gol_casa is not None


class PuntiDiGiornata(BaseModel):
    giornata: int
    punti: float


class AndamentoSquadra(BaseModel):
    squadra: str
    punti: list[PuntiDiGiornata]


class Campionato(BaseModel):
    classifica: list[RigaClassifica]
    partite: list[Partita]
    andamento: list[AndamentoSquadra]
    giornate_disputate: int
    # Quante ne prevede la lega...
    giornate_totali: int
    # ...e quante ne ha davvero il calendario caricato. I due numeri possono
    # non coincidere, ed e' un punto aperto del regolamento (PUNTI_APERTI.md
    # §5): con 10 squadre andata e ritorno fanno 18 giornate, ma l'appendice
    # ne propone 27. Mostrarli tutti e due e' l'unico modo onesto: dire solo
    # «su 27» mentre il calendario finisce alla 18 fa sembrare che manchino
    # delle partite che nessuno ha mai programmato.
    giornate_in_calendario: int
    # Le squadre possono esistere senza che il calendario sia stato importato:
    # la classifica c'e' (tutte a zero) ma non c'e' nessuna partita.
    calendario_importato: bool


def _partite(calendario: pd.DataFrame) -> list[Partita]:
    if calendario.empty:
        return []
    return [
        Partita(
            giornata=int(riga.giornata),
            casa=str(riga.casa),
            trasferta=str(riga.trasferta),
            gol_casa=None if pd.isna(riga.gol_casa) else int(riga.gol_casa),
            gol_trasferta=(
                None if pd.isna(riga.gol_trasferta) else int(riga.gol_trasferta)
            ),
            punti_casa=_numero(riga.punti_casa),
            punti_trasferta=_numero(riga.punti_trasferta),
        )
        for riga in calendario.itertuples()
    ]


def _andamento(tabella: pd.DataFrame) -> list[AndamentoSquadra]:
    if tabella.empty:
        return []
    return [
        AndamentoSquadra(
            squadra=str(squadra),
            punti=[
                PuntiDiGiornata(giornata=int(r.giornata), punti=float(r.punti))
                for r in gruppo.itertuples()
            ],
        )
        for squadra, gruppo in tabella.groupby("squadra", sort=True)
    ]


@rotte.get("/campionato", response_model=Campionato)
def campionato(utente: UtenteDentro) -> Campionato:
    ctx = contesto_di(utente)
    calendario = calendario_dettagliato(ctx.arch)
    tabella = classifica(ctx.arch)

    giocate = (
        calendario[calendario["gol_casa"].notna()] if not calendario.empty else calendario
    )
    disputate = int(giocate["giornata"].max()) if not giocate.empty else 0

    righe = [
        RigaClassifica(
            posizione=int(r["Pos"]),
            squadra=str(r["Squadra"]),
            giocate=int(r["PG"]),
            vinte=int(r["V"]),
            pareggiate=int(r["N"]),
            perse=int(r["P"]),
            gol_fatti=int(r["GF"]),
            gol_subiti=int(r["GS"]),
            differenza_reti=int(r["DR"]),
            punti=int(r["Punti"]),
            punti_fantacalcio=float(r["Punti fantacalcio"]),
        )
        for _, r in tabella.iterrows()
    ]

    programmate = int(calendario["giornata"].max()) if not calendario.empty else 0

    return Campionato(
        classifica=righe,
        partite=_partite(calendario),
        andamento=_andamento(andamento_punti(ctx.arch)),
        giornate_disputate=disputate,
        giornate_totali=ctx.calendario.giornate_totali,
        giornate_in_calendario=programmate,
        calendario_importato=not calendario.empty,
    )
