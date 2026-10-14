"""Giornata: gli scontri diretti, i due campi uno di fronte all'altro, il conto.

E' la pagina della domenica. Tre cose, in quest'ordine: le partite con il
punteggio, le due formazioni disegnate con i punti di ogni giocatore appena i
voti ci sono, e il calcolo — che spetta al presidente.

**Il conto non si fa qui.** Lo fanno `calcola_partita` e `calcola_giornata`,
che hanno i loro test: questa rotta mostra e scrive. Un punteggio ricalcolato
in questo strato sarebbe un secondo regolamento, e il primo a sbagliare
sarebbe quello che nessuno guarda.

Il punteggio provvisorio si vede **prima** di salvarlo: appena i voti sono
caricati, ogni partita mostra come finirebbe. E' lo stesso calcolo che poi
scrive il risultato, non una stima.
"""

from __future__ import annotations

import base64

from fastapi import APIRouter, HTTPException, status
from pydantic import BaseModel, Field

from fantacalcio.data import (
    calendario_dettagliato,
    carica_formazioni,
    carica_giocatori,
    carica_rose,
    carica_voti,
    salva_risultato,
    salva_voti,
)
from fantacalcio.formazioni import (
    EsitoPartita,
    Formazione,
    TabellinoSquadra,
    calcola_partita,
    schieramento,
)
from fantacalcio.giornata import (
    MODELLO_CSV_VOTI,
    VotiNonLeggibili,
    abbinamento,
    calcola_giornata,
    leggi_voti,
)
from fantacalcio.leghe import ModalitaSostituzioni, parametri_di_punteggio

from ..contesto import Contesto, contesto_di
from ..dipendenze import UtenteDentro

rotte = APIRouter(tags=["giornata"])

NON_ELABORABILE = 422


# ---------------------------------------------------------------------------
# Quello che esce
# ---------------------------------------------------------------------------


class InCampo(BaseModel):
    """Un giocatore sul campo. I punti ci sono solo quando i voti ci sono."""

    id: int
    nome: str
    ruoli: list[str]
    punti: float | None = None
    entrato: bool = False
    senza_voto: bool = False
    adattato: bool = False


class Tabellino(BaseModel):
    """Da dove arriva il punteggio di una squadra, voce per voce."""

    totale: float
    gol: int
    modificatore_difesa: float
    malus_adattamento: float
    malus_emergenza: float
    adattati: int
    sostituzioni: list[str]
    senza_voto_rimasti: list[str]


class SquadraDellaPartita(BaseModel):
    squadra_id: int
    squadra: str
    modulo: str | None
    ha_schierato: bool
    reparti: list[list[InCampo]]
    panchina: list[str]
    tabellino: Tabellino | None


class PartitaLetta(BaseModel):
    id: int
    stato: str  # "salvata" | "provvisoria" | "da giocare"
    gol_casa: int | None
    gol_trasferta: int | None
    punti_casa: float | None
    punti_trasferta: float | None
    casa: SquadraDellaPartita
    trasferta: SquadraDellaPartita


class PaginaGiornata(BaseModel):
    giornata: int
    giornate: list[int]
    competizione: str
    competizioni: list[str]
    partite: list[PartitaLetta]
    formazioni_salvate: int
    voti_caricati: int
    calendario_vuoto: bool

    # Solo per chi calcola
    posso_calcolare: bool
    modello_voti: str
    senza_formazione: list[str]


class VotiDaLeggere(BaseModel):
    giornata: int = Field(ge=1)
    # Il file in base64, oppure il testo incollato. Chi carica sceglie: dalla
    # pagina dei voti si arriva piu' spesso con un copia-incolla che con un
    # file, e costringere a salvare un .csv per incollare tre righe e' un
    # passaggio in piu' che nessuno capisce.
    contenuto_base64: str = ""
    testo: str = ""


class VotiLetti(BaseModel):
    messaggio: str
    salvati: int
    senza_voto: int
    non_abbinati: list[str]


class GiornataCalcolata(BaseModel):
    messaggio: str
    calcolate: int
    saltate: int
    avvisi: list[str]


# ---------------------------------------------------------------------------
# Traduzioni
# ---------------------------------------------------------------------------


def _campo(
    formazione: Formazione,
    tabellino: TabellinoSquadra | None,
    nomi: dict[int, str],
    ruoli: dict,
) -> list[list[InCampo]]:
    """I reparti da disegnare.

    Col tabellino si mostra **chi ha davvero giocato**: al posto di chi e'
    rimasto senza voto compare il sostituto entrato. Disegnare i titolari di
    partenza accanto a un punteggio che li ha gia' sostituiti farebbe sembrare
    sbagliato il conto.
    """
    if tabellino is None:
        return [
            [
                InCampo(id=g, nome=nomi.get(g, str(g)), ruoli=list(ruoli.get(g, ())))
                for g in giocatori
            ]
            for _, giocatori in schieramento(formazione)
        ]

    entrati = {s.entrato for s in tabellino.sostituzioni}
    a_zero = set(tabellino.senza_voto)
    adattati = set(tabellino.adattati)
    scorrimento = iter(tabellino.schierati)

    reparti: list[list[InCampo]] = []
    for _, giocatori in schieramento(formazione):
        riga: list[InCampo] = []
        for _ in giocatori:
            _, giocatore, punti = next(scorrimento)
            riga.append(
                InCampo(
                    id=giocatore,
                    nome=nomi.get(giocatore, str(giocatore)),
                    ruoli=list(ruoli.get(giocatore, ())),
                    punti=punti,
                    entrato=giocatore in entrati,
                    senza_voto=giocatore in a_zero and giocatore not in entrati,
                    adattato=giocatore in adattati,
                )
            )
        reparti.append(riga)
    return reparti


def _tabellino(tabellino: TabellinoSquadra, nomi: dict[int, str]) -> Tabellino:
    usciti = {s.uscito for s in tabellino.sostituzioni}
    return Tabellino(
        totale=tabellino.totale,
        gol=tabellino.gol,
        modificatore_difesa=tabellino.modificatore_difesa,
        malus_adattamento=tabellino.malus_adattamento,
        malus_emergenza=tabellino.malus_emergenza,
        adattati=len(tabellino.adattati),
        sostituzioni=[
            f"{nomi.get(s.entrato, '?')} per {nomi.get(s.uscito, '?')}"
            + (" · adattato" if s.adattato else "")
            for s in tabellino.sostituzioni
        ],
        senza_voto_rimasti=[
            nomi.get(g, str(g)) for g in tabellino.senza_voto if g not in usciti
        ],
    )


def _squadra(
    squadra_id: int,
    nome: str,
    formazione: Formazione | None,
    tabellino: TabellinoSquadra | None,
    nomi: dict[int, str],
    ruoli: dict,
) -> SquadraDellaPartita:
    if formazione is None:
        return SquadraDellaPartita(
            squadra_id=squadra_id,
            squadra=nome,
            modulo=None,
            ha_schierato=False,
            reparti=[],
            panchina=[],
            tabellino=None,
        )
    return SquadraDellaPartita(
        squadra_id=squadra_id,
        squadra=nome,
        modulo=formazione.modulo,
        ha_schierato=True,
        reparti=_campo(formazione, tabellino, nomi, ruoli),
        panchina=[nomi.get(g, str(g)) for g in formazione.panchina],
        tabellino=_tabellino(tabellino, nomi) if tabellino else None,
    )


def _ingredienti(ctx: Contesto, giornata: int, competizione: str):
    """Tutto quel che serve a calcolare, letto una volta sola."""
    opzioni = ctx.lega.opzioni if ctx.lega else None
    return {
        "formazioni": carica_formazioni(ctx.arch, giornata, competizione),
        "voti": carica_voti(ctx.arch, giornata),
        "parametri": parametri_di_punteggio(ctx.parametri, ctx.lega),
        "bonus": opzioni.bonus if opzioni else None,
        "fasce": (
            opzioni.fasce_difesa if opzioni and opzioni.modificatore_difesa else ()
        ),
        # Senza sostituzioni automatiche non entra nessuno: chi resta senza
        # voto vale zero, ed e' una scelta della lega, non un caso limite.
        "sostituzioni": (
            opzioni.sostituzioni_massime
            if opzioni and opzioni.sostituzioni_automatiche
            else 0
        ),
        "modalita": (
            opzioni.modalita_sostituzioni if opzioni else ModalitaSostituzioni.BASIC
        ),
        # I moduli della lega servono al **cambio modulo**: quando in panchina
        # nessuno sta in piedi nello schema scelto, la piattaforma ne prova un
        # altro pur di far entrare qualcuno. Senza l'elenco, il cambio non si
        # fa e quel posto resta a zero.
        "moduli": opzioni.moduli_ammessi if opzioni else (),
    }


def _esito(partita, ingredienti, ruoli) -> EsitoPartita | None:
    casa, trasferta = int(partita["casa_id"]), int(partita["trasferta_id"])
    formazioni = ingredienti["formazioni"]
    if casa not in formazioni or trasferta not in formazioni or not ingredienti["voti"]:
        return None
    return calcola_partita(
        formazioni[casa],
        formazioni[trasferta],
        ingredienti["voti"],
        ruoli,
        ingredienti["parametri"],
        ingredienti["bonus"],
        ingredienti["fasce"],
        ingredienti["sostituzioni"],
        ingredienti["modalita"],
        ingredienti["moduli"],
    )


# ---------------------------------------------------------------------------
# La pagina
# ---------------------------------------------------------------------------


@rotte.get("/giornata", response_model=PaginaGiornata)
def pagina(
    utente: UtenteDentro, giornata: int = 0, competizione: str = "CAMPIONATO"
) -> PaginaGiornata:
    import pandas as pd

    ctx = contesto_di(utente)
    opzioni = ctx.lega.opzioni if ctx.lega else None
    competizioni = [c.name for c in opzioni.competizioni] if opzioni else ["CAMPIONATO"]
    if competizione not in competizioni:
        competizione = competizioni[0]

    partite = calendario_dettagliato(ctx.arch)
    if partite.empty:
        return PaginaGiornata(
            giornata=1,
            giornate=[],
            competizione=competizione,
            competizioni=competizioni,
            partite=[],
            formazioni_salvate=0,
            voti_caricati=0,
            calendario_vuoto=True,
            posso_calcolare=utente.puo_importare,
            modello_voti=MODELLO_CSV_VOTI,
            senza_formazione=[],
        )

    della_competizione = partite
    if "competizione" in partite.columns:
        della_competizione = partite[partite["competizione"].astype(str) == competizione]

    giornate = sorted({int(g) for g in della_competizione["giornata"].dropna()})
    if not giornate:
        return PaginaGiornata(
            giornata=1,
            giornate=[],
            competizione=competizione,
            competizioni=competizioni,
            partite=[],
            formazioni_salvate=0,
            voti_caricati=0,
            calendario_vuoto=True,
            posso_calcolare=utente.puo_importare,
            modello_voti=MODELLO_CSV_VOTI,
            senza_formazione=[],
        )

    if giornata not in giornate:
        giocate = della_competizione[della_competizione["gol_casa"].notna()]
        prossima = (int(giocate["giornata"].max()) if not giocate.empty else 0) + 1
        giornata = prossima if prossima in giornate else giornate[-1]

    del_turno = della_competizione[
        della_competizione["giornata"].astype("Int64") == giornata
    ]

    rose = carica_rose(ctx.arch)
    nomi_squadre = {id_: r.squadra.nome for id_, r in rose.items()}
    giocatori = carica_giocatori(ctx.arch)
    nomi = {g.id: g.nome for g in giocatori.values()}
    ruoli = {g.id: g.ruoli for g in giocatori.values()}

    ingredienti = _ingredienti(ctx, giornata, competizione)
    formazioni = ingredienti["formazioni"]

    lette: list[PartitaLetta] = []
    senza_formazione: set[str] = set()
    for _, partita in del_turno.iterrows():
        casa_id, trasferta_id = int(partita["casa_id"]), int(partita["trasferta_id"])
        for squadra in (casa_id, trasferta_id):
            if squadra not in formazioni:
                senza_formazione.add(nomi_squadre.get(squadra, str(squadra)))

        esito = _esito(partita, ingredienti, ruoli)
        scritta = not pd.isna(partita.get("gol_casa"))

        lette.append(
            PartitaLetta(
                id=int(partita["id"]),
                stato="salvata"
                if scritta
                else ("provvisoria" if esito else "da giocare"),
                gol_casa=int(partita["gol_casa"])
                if scritta
                else (esito.casa.gol if esito else None),
                gol_trasferta=int(partita["gol_trasferta"])
                if scritta
                else (esito.trasferta.gol if esito else None),
                punti_casa=float(partita["punti_casa"])
                if scritta
                else (esito.casa.totale if esito else None),
                punti_trasferta=float(partita["punti_trasferta"])
                if scritta
                else (esito.trasferta.totale if esito else None),
                casa=_squadra(
                    casa_id,
                    nomi_squadre.get(casa_id, str(casa_id)),
                    formazioni.get(casa_id),
                    esito.casa if esito else None,
                    nomi,
                    ruoli,
                ),
                trasferta=_squadra(
                    trasferta_id,
                    nomi_squadre.get(trasferta_id, str(trasferta_id)),
                    formazioni.get(trasferta_id),
                    esito.trasferta if esito else None,
                    nomi,
                    ruoli,
                ),
            )
        )

    return PaginaGiornata(
        giornata=giornata,
        giornate=giornate,
        competizione=competizione,
        competizioni=competizioni,
        partite=lette,
        formazioni_salvate=sum(
            1
            for _, p in del_turno.iterrows()
            for s in (int(p["casa_id"]), int(p["trasferta_id"]))
            if s in formazioni
        ),
        voti_caricati=len(ingredienti["voti"]),
        calendario_vuoto=False,
        posso_calcolare=utente.puo_importare,
        modello_voti=MODELLO_CSV_VOTI,
        senza_formazione=sorted(senza_formazione),
    )


# ---------------------------------------------------------------------------
# Voti e calcolo: del presidente
# ---------------------------------------------------------------------------


def _solo_chi_calcola(utente) -> Contesto:
    if not utente.puo_importare:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="I voti li carica il presidente di lega, che poi calcola la giornata.",
        )
    return contesto_di(utente)


@rotte.post("/giornata/voti", response_model=VotiLetti)
def carica_i_voti(richiesta: VotiDaLeggere, utente: UtenteDentro) -> VotiLetti:
    """Legge i voti e li salva. Chi non si abbina si dice, non sparisce."""
    ctx = _solo_chi_calcola(utente)

    if richiesta.contenuto_base64:
        try:
            contenuto: bytes | str = base64.b64decode(
                richiesta.contenuto_base64, validate=True
            )
        except Exception as errore:  # noqa: BLE001 - base64 alza tipi diversi
            raise HTTPException(
                status_code=NON_ELABORABILE,
                detail="Il file non e' leggibile: riprova a caricarlo.",
            ) from errore
    else:
        contenuto = richiesta.testo

    if not str(contenuto).strip():
        raise HTTPException(
            status_code=NON_ELABORABILE,
            detail="Non ho ne' un file ne' del testo da leggere.",
        )

    per_nome, per_id = abbinamento(carica_giocatori(ctx.arch))
    try:
        esito = leggi_voti(contenuto, richiesta.giornata, per_nome, per_id)
    except VotiNonLeggibili as errore:
        raise HTTPException(status_code=NON_ELABORABILE, detail=str(errore)) from errore

    quanti = salva_voti(ctx.arch, esito.voti)

    messaggio = f"{quanti} voti salvati per la giornata {richiesta.giornata}."
    if esito.senza_voto:
        messaggio += f" {esito.senza_voto} senza voto."
    return VotiLetti(
        messaggio=messaggio,
        salvati=quanti,
        senza_voto=esito.senza_voto,
        non_abbinati=esito.non_abbinati,
    )


@rotte.post("/giornata/calcola", response_model=GiornataCalcolata)
def calcola(
    utente: UtenteDentro, giornata: int, competizione: str = "CAMPIONATO"
) -> GiornataCalcolata:
    """Scrive gol e fantapunti delle partite di questa giornata.

    Si puo' rifare: quando arrivano voti corretti, si ricalcola e si
    riscrive. Una squadra senza formazione non fa saltare l'intera giornata —
    si salta quella partita e lo si dice.
    """
    ctx = _solo_chi_calcola(utente)

    partite = calendario_dettagliato(ctx.arch)
    if partite.empty:
        raise HTTPException(status_code=NON_ELABORABILE, detail="Il calendario e' vuoto.")
    if "competizione" in partite.columns:
        partite = partite[partite["competizione"].astype(str) == competizione]
    del_turno = partite[partite["giornata"].astype("Int64") == giornata]
    if del_turno.empty:
        raise HTTPException(
            status_code=NON_ELABORABILE,
            detail=f"Nessuna partita in calendario per la giornata {giornata}.",
        )

    giocatori = carica_giocatori(ctx.arch)
    ruoli = {g.id: g.ruoli for g in giocatori.values()}
    ingredienti = _ingredienti(ctx, giornata, competizione)

    esito = calcola_giornata(
        giornata,
        [
            {
                "id": int(p["id"]),
                "casa_id": int(p["casa_id"]),
                "trasferta_id": int(p["trasferta_id"]),
            }
            for _, p in del_turno.iterrows()
        ],
        ingredienti["formazioni"],
        ingredienti["voti"],
        ruoli,
        ingredienti["parametri"],
        ingredienti["bonus"],
        ingredienti["fasce"],
        ingredienti["sostituzioni"],
        ingredienti["modalita"],
        ingredienti["moduli"],
    )

    scritte = 0
    for risultato in esito.risultati:
        if not risultato.calcolata:
            continue
        salva_risultato(
            ctx.arch,
            risultato.partita_id,
            risultato.esito.casa.gol,
            risultato.esito.trasferta.gol,
            risultato.esito.casa.totale,
            risultato.esito.trasferta.totale,
        )
        scritte += 1

    saltate = len(esito.risultati) - esito.calcolate
    if not scritte:
        messaggio = "Non c'era niente da calcolare."
    else:
        partite_dette = "partita" if scritte == 1 else "partite"
        messaggio = f"Giornata {giornata}: {scritte} {partite_dette} calcolate."
        if saltate:
            messaggio += f" {saltate} saltate per formazione mancante."
    return GiornataCalcolata(
        messaggio=messaggio,
        calcolate=scritte,
        saltate=saltate,
        avvisi=esito.avvisi,
    )
