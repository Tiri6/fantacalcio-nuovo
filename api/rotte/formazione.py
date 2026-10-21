"""Formazione: chi mandi in campo, e cosa si vede quando la giornata chiude.

Due momenti che non si mescolano, come su Streamlit: finche' la giornata e'
aperta si compone la propria formazione, dal blocco in poi si guardano quelle
di tutti.

**La tabella Mantra non arriva in TypeScript.** Quali ruoli stanno in una
casella, chi ci si adatta pagando il malus e chi non ci puo' proprio stare lo
decide `esito_casella`, in Python, con i suoi test. Per il modulo scelto
questa rotta manda, casella per casella, chi la occupa di diritto e chi la
occuperebbe adattandosi: la pagina mostra due elenchi, non ricalcola una
regola. Riscritta di la', sarebbe la copia che diverge — e divergerebbe sul
pezzo di regolamento piu' intricato che abbiamo.

Per lo stesso motivo il modulo e' un parametro della GET: cambiarlo cambia le
caselle, quindi cambia le liste, quindi si richiede al server.
"""

from __future__ import annotations

from datetime import datetime

from fastapi import APIRouter, HTTPException, status
from pydantic import BaseModel, Field

from fantacalcio.competizioni import inizio_giornata
from fantacalcio.data import (
    calendario_dettagliato,
    carica_formazioni,
    carica_giocatori,
    carica_rose,
    carica_titolari_per_giornata,
    carica_voti_stagione,
    salva_formazione,
)
from fantacalcio.formazioni import (
    TITOLARI,
    Formazione,
    adattamenti,
    esito_casella,
    formazione_suggerita,
    frase_adattamenti,
    leggi_modulo,
    puo_occupare,
    schieramento,
    stato_blocco,
    valida,
)
from fantacalcio.leghe import ModalitaSostituzioni
from fantacalcio.mantra import Esito
from fantacalcio.statistiche import statistiche_stagione

from ..contesto import Contesto, contesto_di
from ..dipendenze import UtenteDentro

rotte = APIRouter(tags=["formazione"])

NON_ELABORABILE = 422


# ---------------------------------------------------------------------------
# Quello che esce
# ---------------------------------------------------------------------------


class GiocatoreScelta(BaseModel):
    """Un giocatore come lo vede chi compone: nome e ruoli, niente altro."""

    id: int
    nome: str
    ruoli: list[str]
    #: Dalla nostra storia, calcolati dal server: la pagina li stampa e basta.
    #: `None` = mai preso voto, e la pagina scrive un trattino (non uno zero).
    media_voto: float | None = None
    #: Giornate con voto e quota di quelle giocate da titolare (0-100).
    presenze: int = 0
    titolare_pct: int | None = None


class CasellaLetta(BaseModel):
    """Un posto del modulo, con chi ci puo' finire.

    `liberi` sono quelli che la casella ammette di suo, `adattati` quelli che
    ci starebbero pagando il malus. Due elenchi e non uno solo ordinato: la
    scelta che costa deve restare possibile senza capitare per sbaglio.
    """

    indice: int
    etichetta: str
    reparto: str
    liberi: list[int]
    adattati: list[int]


class Blocco(BaseModel):
    modificabile: bool
    motivo: str
    inizio: str | None
    mancano_secondi: int | None


class SquadraInCampo(BaseModel):
    """Una formazione salvata, gia' divisa per reparti da disegnare."""

    squadra_id: int
    squadra: str
    modulo: str
    reparti: list[list[GiocatoreScelta]]
    panchina: list[GiocatoreScelta]


class PaginaFormazione(BaseModel):
    giornata: int
    giornate_totali: int
    competizione: str
    competizioni: list[str]
    blocco: Blocco

    # Chi compone
    mia_squadra_id: int | None
    posso_schierare: bool
    avviso: str | None

    # Il modulo e le sue caselle
    moduli: list[str]
    modulo: str
    modulo_ufficiale: bool
    difensori: int
    centrocampisti: int
    attaccanti: int
    caselle: list[CasellaLetta]
    titolari_richiesti: int
    panchinari: int

    # Le regole di adattamento, dette prima e non dopo
    adattamento_ammesso: bool
    malus_adattamento: float
    modalita_sostituzioni: str

    rosa: list[GiocatoreScelta]
    titolari: list[int]
    panchina: list[int]

    # Quello che hanno fatto gli altri
    squadre: list[SquadraInCampo]
    mancanti: list[str]
    schierate: int
    totali: int


class Salvata(BaseModel):
    salvata: bool
    messaggio: str


class DaSchierare(BaseModel):
    giornata: int = Field(ge=1)
    competizione: str = "CAMPIONATO"
    modulo: str
    titolari: list[int]
    panchina: list[int] = []


# ---------------------------------------------------------------------------
# Traduzioni
# ---------------------------------------------------------------------------


def _giocatore(
    id_: int, nomi: dict[int, str], ruoli: dict, statistiche: dict | None = None
) -> GiocatoreScelta:
    stat = (statistiche or {}).get(id_)
    return GiocatoreScelta(
        id=id_,
        nome=nomi.get(id_, str(id_)),
        ruoli=list(ruoli.get(id_, ())),
        media_voto=stat.media if stat else None,
        presenze=stat.presenze if stat else 0,
        titolare_pct=stat.percentuale_titolare if stat else None,
    )


def _competizioni(ctx: Contesto) -> list[str]:
    if ctx.lega is None:
        return ["CAMPIONATO"]
    return [c.name for c in ctx.lega.opzioni.competizioni]


# ---------------------------------------------------------------------------
# La pagina
# ---------------------------------------------------------------------------


@rotte.get("/formazione", response_model=PaginaFormazione)
def pagina(
    utente: UtenteDentro,
    giornata: int = 0,
    competizione: str = "CAMPIONATO",
    modulo: str = "",
) -> PaginaFormazione:
    """Tutto quel che serve a comporre e a guardare, in una richiesta sola.

    `giornata` a zero vuol dire «quella giusta adesso»: la prima non ancora
    disputata. Si passa esplicitamente solo quando si cambia dalla tendina,
    cosi' un ricarico non riporta indietro chi stava guardando la 12.
    """
    ctx = contesto_di(utente)
    opzioni = ctx.lega.opzioni if ctx.lega else None
    competizioni = _competizioni(ctx)
    if competizione not in competizioni:
        competizione = competizioni[0]

    partite = calendario_dettagliato(ctx.arch)
    giornate_totali = (
        opzioni.giornate_totali if opzioni else ctx.calendario.giornate_totali
    )
    if giornata < 1:
        giocate = partite[partite["gol_casa"].notna()] if not partite.empty else partite
        disputate = (
            int(giocate["giornata"].max())
            if not partite.empty and not giocate.empty
            else 0
        )
        giornata = min(disputate + 1, max(giornate_totali, 1))

    inizio = inizio_giornata(partite, giornata, competizione)
    blocco = stato_blocco(inizio, datetime.now())

    rose = carica_rose(ctx.arch)
    giocatori = carica_giocatori(ctx.arch)
    nomi = {g.id: g.nome for g in giocatori.values()}
    ruoli = {g.id: g.ruoli for g in giocatori.values()}
    salvate = carica_formazioni(ctx.arch, giornata, competizione)
    statistiche = statistiche_stagione(
        carica_voti_stagione(ctx.arch), carica_titolari_per_giornata(ctx.arch)
    )

    moduli = list(opzioni.moduli_ammessi) if opzioni else ["3-4-3"]
    mia = utente.squadra_id if utente.squadra_id in rose else None
    corrente = salvate.get(mia) if mia else None

    if modulo not in moduli:
        # Il modulo di chi ha gia' schierato, altrimenti il primo ammesso.
        modulo = (
            corrente.modulo
            if corrente and corrente.modulo in moduli
            else (moduli[0] if moduli else "3-4-3")
        )

    schema = leggi_modulo(modulo)
    modalita = opzioni.modalita_sostituzioni if opzioni else ModalitaSostituzioni.BASIC
    adattamento_ammesso = modalita is not ModalitaSostituzioni.EASY
    panchinari = opzioni.panchinari if opzioni else 12

    in_rosa = [c.giocatore_id for c in rose[mia].contratti] if mia else []

    # La proposta: quella salvata se il modulo e' lo stesso, altrimenti una
    # valida da correggere. Cambiare modulo cambia i posti, e la vecchia non
    # vale piu' come punto di partenza.
    avviso = None
    if corrente and corrente.modulo == modulo:
        base = corrente
        non_va_piu = valida(corrente, ruoli, set(in_rosa), modalita)
        if non_va_piu:
            avviso = (
                "La formazione che avevi salvato non e' piu' valida: "
                + non_va_piu[0]
                + " Qui sotto trovi una versione corretta, ma vale solo se la "
                "salvi di nuovo."
            )
    elif in_rosa:
        base = formazione_suggerita(
            mia or 0, giornata, modulo, in_rosa, ruoli, panchinari=panchinari
        )
    else:
        base = Formazione(squadra_id=mia or 0, giornata=giornata, modulo=modulo)

    caselle = []
    for indice, casella in enumerate(schema.caselle):
        liberi = [
            g
            for g in in_rosa
            if esito_casella(casella, ruoli.get(g, ()), modulo) is Esito.LIBERA
        ]
        adattati = (
            [
                g
                for g in in_rosa
                if g not in liberi and puo_occupare(casella, ruoli.get(g, ()), modulo)
            ]
            if adattamento_ammesso
            else []
        )
        caselle.append(
            CasellaLetta(
                indice=indice,
                etichetta=casella.etichetta
                if schema.ufficiale
                else casella.reparto.etichetta,
                reparto=casella.reparto.etichetta,
                liberi=liberi,
                adattati=adattati,
            )
        )

    squadre = [
        SquadraInCampo(
            squadra_id=squadra_id,
            squadra=rose[squadra_id].squadra.nome
            if squadra_id in rose
            else str(squadra_id),
            modulo=formazione.modulo,
            reparti=[
                [_giocatore(g, nomi, ruoli) for g in giocatori_del_reparto]
                for _, giocatori_del_reparto in schieramento(formazione)
            ],
            panchina=[_giocatore(g, nomi, ruoli) for g in formazione.panchina],
        )
        for squadra_id, formazione in sorted(salvate.items())
    ]

    return PaginaFormazione(
        giornata=giornata,
        giornate_totali=max(giornate_totali, 1),
        competizione=competizione,
        competizioni=competizioni,
        blocco=Blocco(
            modificabile=blocco.modificabile,
            motivo=blocco.motivo,
            inizio=inizio.isoformat() if inizio else None,
            mancano_secondi=int(blocco.mancano.total_seconds())
            if blocco.mancano
            else None,
        ),
        mia_squadra_id=mia,
        posso_schierare=bool(mia) and blocco.modificabile and bool(in_rosa),
        avviso=avviso,
        moduli=moduli,
        modulo=modulo,
        modulo_ufficiale=schema.ufficiale,
        difensori=schema.difensori,
        centrocampisti=schema.centrocampisti,
        attaccanti=schema.attaccanti,
        caselle=caselle,
        titolari_richiesti=TITOLARI,
        panchinari=panchinari,
        adattamento_ammesso=adattamento_ammesso,
        malus_adattamento=abs(ctx.parametri.malus_adattamento),
        modalita_sostituzioni=modalita.etichetta,
        rosa=[_giocatore(g, nomi, ruoli, statistiche) for g in in_rosa],
        titolari=list(base.titolari),
        panchina=[g for g in base.panchina if g in in_rosa][:panchinari],
        squadre=squadre,
        mancanti=sorted(rose[s].squadra.nome for s in rose if s not in salvate),
        schierate=len(salvate),
        totali=len(rose),
    )


@rotte.post("/formazione", response_model=Salvata)
def schiera(richiesta: DaSchierare, utente: UtenteDentro) -> Salvata:
    """Salva la propria formazione, se la giornata e' ancora aperta.

    Il blocco si ricontrolla qui e non solo nella pagina: l'orario e' il
    confine fra «schierata in tempo» e «schierata dopo aver visto le altre»,
    e un bottone nascosto non e' un controllo.
    """
    ctx = contesto_di(utente)
    rose = carica_rose(ctx.arch)
    if utente.squadra_id not in rose:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Non hai una squadra in questa lega.",
        )

    partite = calendario_dettagliato(ctx.arch)
    blocco = stato_blocco(
        inizio_giornata(partite, richiesta.giornata, richiesta.competizione),
        datetime.now(),
    )
    if not blocco.modificabile:
        raise HTTPException(status_code=NON_ELABORABILE, detail=blocco.motivo)

    # Modulo e competizione si ricontrollano qui, non solo nella GET che li
    # corregge: la rotta si chiama anche a mano, e un modulo che la lega non
    # ammette e' una regola saltata — `valida` non puo' accorgersene, perche'
    # guarda se il modulo e' *leggibile*, non se e' *consentito*.
    opzioni = ctx.lega.opzioni if ctx.lega else None
    if opzioni:
        if richiesta.modulo not in opzioni.moduli_ammessi:
            raise HTTPException(
                status_code=NON_ELABORABILE,
                detail=(
                    f"Il modulo {richiesta.modulo} non e' fra quelli ammessi da "
                    f"questa lega."
                ),
            )
        if richiesta.competizione not in [c.name for c in opzioni.competizioni]:
            raise HTTPException(
                status_code=NON_ELABORABILE,
                detail="Questa lega non gioca quella competizione.",
            )

    giocatori = carica_giocatori(ctx.arch)
    ruoli = {g.id: g.ruoli for g in giocatori.values()}
    in_rosa = {c.giocatore_id for c in rose[utente.squadra_id].contratti}
    modalita = (
        ctx.lega.opzioni.modalita_sostituzioni if ctx.lega else ModalitaSostituzioni.BASIC
    )

    proposta = Formazione(
        squadra_id=utente.squadra_id,
        giornata=richiesta.giornata,
        modulo=richiesta.modulo,
        titolari=tuple(richiesta.titolari),
        panchina=tuple(richiesta.panchina),
        competizione=richiesta.competizione,
    )

    problemi = valida(proposta, ruoli, in_rosa, modalita)
    if problemi:
        # Tutti, non il primo: chi schiera vuole sapere quante cose deve
        # sistemare, non scoprirle una alla volta.
        raise HTTPException(status_code=NON_ELABORABILE, detail=" ".join(problemi))

    salva_formazione(ctx.arch, proposta)

    fuori_posizione = adattamenti(proposta, ruoli)
    messaggio = f"Formazione salvata per la giornata {richiesta.giornata}."
    frase = frase_adattamenti(len(fuori_posizione), ctx.parametri.malus_adattamento)
    if frase:
        messaggio += f" {frase}"
    return Salvata(salvata=True, messaggio=messaggio)
