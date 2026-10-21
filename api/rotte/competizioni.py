"""Calendario, Coppa Italia e F1 Rush: le tre pagine che parlano di gare.

Stanno insieme perche' leggono le stesse due cose — il calendario e le regole
della lega — e perche' **due di loro possono non esistere**. Coppa e F1 Rush
si giocano solo se la lega le ha attivate: le rotte lo dicono con `si_gioca`,
e il menu non mostra la voce. Una pagina che parla di una competizione
inesistente e' peggio di una voce mancante.

Niente regole qui dentro: il tabellone lo compone `RegoleCoppa`, la
corrispondenza fra weekend di Serie A e giornate di lega `costruisci_weekend`,
la classifica a tappe `classifica_f1`. Questa e' traduzione.
"""

from __future__ import annotations

import pandas as pd
from fastapi import APIRouter, HTTPException, status
from pydantic import BaseModel

from fantacalcio.competizioni import (
    GIORNATE_SERIE_A,
    PRIMA_GIORNATA_SERIE_A,
    CriterioF1Rush,
    TipoCompetizione,
    classifica_f1,
    costruisci_weekend,
    crea_titolo,
    giornate_f1_rush,
    titolo_esistente,
)
from fantacalcio.data import (
    calendario_dettagliato,
    carica_albo,
    carica_squadre,
    prossimo_id,
    salva_titolo,
)
from fantacalcio.leghe import puo_modificare_regole
from fantacalcio.vista import tappe_f1

from ..contesto import Contesto, contesto_di
from ..dipendenze import UtenteDentro

rotte = APIRouter(tags=["competizioni"])

NON_ELABORABILE = 422


# ---------------------------------------------------------------------------
# Calendario
# ---------------------------------------------------------------------------


class PartitaInCalendario(BaseModel):
    giornata: int
    casa: str
    trasferta: str
    gol_casa: int | None
    gol_trasferta: int | None
    punti_casa: float | None
    punti_trasferta: float | None


class Weekend(BaseModel):
    numero: int
    serie_a: int
    nella_lega: str


class PaginaCalendario(BaseModel):
    squadre: list[str]
    giornate_disputate: int
    giornate_totali: int
    partite_giocate: int
    partite: list[PartitaInCalendario]
    senza_partite: bool
    # La corrispondenza fra i weekend di Serie A e le giornate della lega non
    # ha bisogno delle partite: si costruisce dalle regole. E' il motivo per
    # cui la pagina resta utile proprio a inizio stagione, quando serve di piu'.
    weekend: list[Weekend]
    gioca_coppa: bool
    # Da quale giornata di Serie A parte il campionato: e' un'opzione della
    # lega, qui si legge e basta. Chi puo' cambiarla lo dice `posso_modificare`
    # (la stessa regola della pagina delle regole, calcolata dal server).
    prima_serie_a: int
    serie_a_totali: int
    posso_modificare: bool


@rotte.get("/calendario", response_model=PaginaCalendario)
def calendario(utente: UtenteDentro, fino_a: int = GIORNATE_SERIE_A) -> PaginaCalendario:
    ctx = contesto_di(utente)
    opzioni = ctx.lega.opzioni if ctx.lega else None
    partite = calendario_dettagliato(ctx.arch)
    vuoto = partite.empty

    prima_serie_a = opzioni.prima_giornata_serie_a if opzioni else PRIMA_GIORNATA_SERIE_A
    posso_modificare = puo_modificare_regole(utente, ctx.lega)
    # «Fino alla 2ª» partendo dalla 10ª non vuol dire niente, e darebbe una
    # tabella vuota senza spiegare perche'. Si tiene l'inizio e si allunga la
    # fine, che e' la lettura piu' probabile di chi ha sbagliato a digitare.
    fino_a = max(prima_serie_a, min(fino_a, GIORNATE_SERIE_A))

    turni = costruisci_weekend(
        giornate_serie_a=fino_a,
        giornate_campionato=opzioni.giornate_totali
        if opzioni
        else ctx.calendario.giornate_totali,
        regole_coppa=opzioni.regole_coppa if opzioni and opzioni.coppa_italia else None,
        prima_giornata_serie_a=prima_serie_a,
        regole_f1_rush=opzioni.regole_f1_rush if opzioni and opzioni.f1_rush else None,
    )

    if vuoto:
        return PaginaCalendario(
            squadre=[],
            giornate_disputate=0,
            giornate_totali=0,
            partite_giocate=0,
            partite=[],
            senza_partite=True,
            weekend=[
                Weekend(numero=i, serie_a=t.giornata_serie_a, nella_lega=t.descrizione)
                for i, t in enumerate(turni, start=1)
            ],
            gioca_coppa=bool(opzioni and opzioni.coppa_italia),
            prima_serie_a=prima_serie_a,
            serie_a_totali=GIORNATE_SERIE_A,
            posso_modificare=posso_modificare,
        )

    giocate = partite[partite["gol_casa"].notna()]
    return PaginaCalendario(
        squadre=sorted(set(partite["casa"]) | set(partite["trasferta"])),
        giornate_disputate=int(giocate["giornata"].max()) if not giocate.empty else 0,
        giornate_totali=int(partite["giornata"].max()),
        partite_giocate=len(giocate),
        partite=[
            PartitaInCalendario(
                giornata=int(r.giornata),
                casa=r.casa,
                trasferta=r.trasferta,
                gol_casa=None if pd.isna(r.gol_casa) else int(r.gol_casa),
                gol_trasferta=None if pd.isna(r.gol_casa) else int(r.gol_trasferta),
                punti_casa=None if pd.isna(r.gol_casa) else float(r.punti_casa),
                punti_trasferta=None if pd.isna(r.gol_casa) else float(r.punti_trasferta),
            )
            for r in partite.itertuples()
        ],
        senza_partite=False,
        weekend=[
            Weekend(numero=i, serie_a=t.giornata_serie_a, nella_lega=t.descrizione)
            for i, t in enumerate(turni, start=1)
        ],
        gioca_coppa=bool(opzioni and opzioni.coppa_italia),
        prima_serie_a=prima_serie_a,
        serie_a_totali=GIORNATE_SERIE_A,
        posso_modificare=posso_modificare,
    )


# ---------------------------------------------------------------------------
# Coppa Italia
# ---------------------------------------------------------------------------


class FaseDiCoppa(BaseModel):
    fase: str
    quando: str
    stato: str


class PaginaCoppa(BaseModel):
    si_gioca: bool
    formato: str
    squadre_ammesse: int
    a_gironi: bool
    gironi: int
    squadre_per_girone: int
    giornate_di_girone: int
    qualificate_per_girone: int
    squadre_a_eliminazione: int
    turni: int
    nomi_turni: list[str]
    prima_giornata: int
    ogni_quante_giornate: int
    teste_di_serie: bool
    spareggio_ai_fantapunti: bool
    tabellone: list[FaseDiCoppa]
    # Con le teste di serie si vede chi passerebbe oggi, e con chi.
    ammesse: list[str]
    accoppiamenti: list[tuple[str, str]]


def _coppa(ctx: Contesto) -> PaginaCoppa:
    opzioni = ctx.lega.opzioni if ctx.lega else None
    if opzioni is None or not opzioni.coppa_italia:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Questa lega non gioca la Coppa Italia.",
        )

    regole = opzioni.regole_coppa
    partite = calendario_dettagliato(ctx.arch)
    giocate = partite[partite["gol_casa"].notna()] if not partite.empty else partite
    disputate = (
        int(giocate["giornata"].max()) if not partite.empty and not giocate.empty else 0
    )

    nomi_turni = [regole.nome_turno(n) for n in range(1, regole.turni + 1)]

    if regole.a_gironi:
        # Coi gironi i turni non cadono a giornate fisse di campionato:
        # vengono dopo, di fila. Mostrare «G5, G9, G13» sarebbe un calendario
        # inventato.
        tabellone = [
            FaseDiCoppa(
                fase=f"Girone — {n}ª giornata",
                quando="dopo il campionato",
                stato="",
            )
            for n in range(1, regole.giornate_di_girone + 1)
        ] + [
            FaseDiCoppa(fase=nome, quando="dopo i gironi", stato="")
            for nome in nomi_turni
        ]
    else:
        tabellone = [
            FaseDiCoppa(
                fase=regole.nome_turno(numero),
                quando=f"G{giornata}",
                stato="Disputato" if disputate >= giornata else "Da giocare",
            )
            for numero, giornata in enumerate(regole.giornate_dei_turni(), start=1)
        ]

    ammesse: list[str] = []
    accoppiamenti: list[tuple[str, str]] = []
    if regole.teste_di_serie and not regole.a_gironi:
        from fantacalcio.vista import classifica

        tabella = classifica(ctx.arch)
        if not tabella.empty:
            ammesse = list(tabella.head(regole.squadre_ammesse)["Squadra"])
            if len(ammesse) == regole.squadre_ammesse:
                # Tabellone classico: la prima incontra l'ultima ammessa.
                accoppiamenti = [
                    (alta, bassa)
                    for indice, (alta, bassa) in enumerate(
                        zip(ammesse, reversed(ammesse), strict=True)
                    )
                    if indice < len(ammesse) // 2
                ]

    return PaginaCoppa(
        si_gioca=True,
        formato=regole.formato.etichetta,
        squadre_ammesse=regole.squadre_ammesse,
        a_gironi=regole.a_gironi,
        gironi=regole.gironi,
        squadre_per_girone=regole.squadre_per_girone,
        giornate_di_girone=regole.giornate_di_girone,
        qualificate_per_girone=regole.qualificate_per_girone,
        squadre_a_eliminazione=regole.squadre_a_eliminazione,
        turni=regole.turni,
        nomi_turni=nomi_turni,
        prima_giornata=regole.prima_giornata,
        ogni_quante_giornate=regole.ogni_quante_giornate,
        teste_di_serie=regole.teste_di_serie,
        spareggio_ai_fantapunti=regole.spareggio_ai_fantapunti,
        tabellone=tabellone,
        ammesse=ammesse,
        accoppiamenti=accoppiamenti,
    )


@rotte.get("/coppa", response_model=PaginaCoppa)
def coppa(utente: UtenteDentro) -> PaginaCoppa:
    return _coppa(contesto_di(utente))


# ---------------------------------------------------------------------------
# F1 Rush Finale
# ---------------------------------------------------------------------------


class RigaF1(BaseModel):
    posizione: int
    squadra: str
    punti: float
    vittorie_di_tappa: int
    fantapunti: float


class TappaF1(BaseModel):
    titolo: str
    podio: list[str]


class PaginaF1(BaseModel):
    si_gioca: bool
    giornate_serie_a: int
    prima_giornata: int
    ultima_giornata: int
    criterio: str
    punti_per_posizione: list[int]
    classifica: list[RigaF1]
    tappe: list[TappaF1]
    # Il calendario non sempre dice a quale giornata di Serie A corrisponde un
    # turno: senza, si usano le ultime giornate di lega e lo si dichiara.
    senza_giornate_serie_a: bool
    vincitrice: str | None
    posso_assegnare: bool
    squadre: list[str]


def _f1(ctx: Contesto, utente) -> PaginaF1:
    opzioni = ctx.lega.opzioni if ctx.lega else None
    if opzioni is None or not opzioni.f1_rush:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Questa lega non gioca la F1 Rush.",
        )

    regole = opzioni.regole_f1_rush
    turni = giornate_f1_rush(regole=regole)
    tappe = tappe_f1(ctx.arch, regole)
    righe = classifica_f1([t["punti"] for t in tappe], regole)

    titoli = carica_albo(ctx.arch, ctx.lega.id if ctx.lega else None)
    gia_vinta = titolo_esistente(
        titoli, TipoCompetizione.F1_RUSH, ctx.lega.stagione if ctx.lega else ""
    )
    squadre = sorted(s.nome for s in carica_squadre(ctx.arch).values())
    if righe:
        prima = righe[0].squadra
        squadre = [prima] + [n for n in squadre if n != prima]

    return PaginaF1(
        si_gioca=True,
        giornate_serie_a=regole.giornate_serie_a,
        prima_giornata=turni[0],
        ultima_giornata=turni[-1],
        criterio=regole.criterio.etichetta,
        punti_per_posizione=list(regole.punti_per_posizione)
        if regole.criterio is CriterioF1Rush.PUNTI_PER_POSIZIONE
        else [],
        classifica=[
            RigaF1(
                posizione=posizione,
                squadra=r.squadra,
                punti=r.punti,
                vittorie_di_tappa=r.vittorie_di_tappa,
                fantapunti=r.fantapunti,
            )
            for posizione, r in enumerate(righe, start=1)
        ],
        tappe=[
            TappaF1(
                titolo=f"{t['serie_a']}ª di Serie A"
                if t["serie_a"]
                else f"{t['giornata']}ª di lega",
                podio=[
                    f"{nome} {punti:.1f}"
                    for nome, punti in sorted(t["punti"].items(), key=lambda v: -v[1])[:3]
                ],
            )
            for t in tappe
        ],
        senza_giornate_serie_a=bool(tappe) and all(t["serie_a"] is None for t in tappe),
        vincitrice=gia_vinta.squadra_nome if gia_vinta else None,
        posso_assegnare=bool(
            ctx.lega and (utente.id == ctx.lega.admin_id or utente.puo_importare)
        ),
        squadre=squadre,
    )


@rotte.get("/f1-rush", response_model=PaginaF1)
def f1_rush(utente: UtenteDentro) -> PaginaF1:
    return _f1(contesto_di(utente), utente)


class Vincitrice(BaseModel):
    squadra: str


@rotte.post("/f1-rush/vincitrice", response_model=PaginaF1)
def assegna(richiesta: Vincitrice, utente: UtenteDentro) -> PaginaF1:
    """Registra la vincitrice nell'albo d'oro."""
    ctx = contesto_di(utente)
    pagina = _f1(ctx, utente)
    if not pagina.posso_assegnare:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="L'albo d'oro lo tiene chi amministra la lega.",
        )
    if pagina.vincitrice:
        raise HTTPException(
            status_code=NON_ELABORABILE,
            detail=f"La F1 Rush di questa stagione e' gia' di {pagina.vincitrice}.",
        )

    squadre = carica_squadre(ctx.arch)
    trovata = next((s for s in squadre.values() if s.nome == richiesta.squadra), None)
    if trovata is None:
        raise HTTPException(
            status_code=NON_ELABORABILE,
            detail=f"«{richiesta.squadra}» non e' una squadra di questa lega.",
        )

    salva_titolo(
        ctx.arch,
        crea_titolo(
            id_=prossimo_id(ctx.arch, "albo"),
            lega_id=ctx.lega.id if ctx.lega else None,
            competizione=TipoCompetizione.F1_RUSH,
            stagione=ctx.lega.stagione if ctx.lega else "",
            squadra_nome=trovata.nome,
            squadra_id=trovata.id,
        ),
    )
    return _f1(contesto_di(utente), utente)
