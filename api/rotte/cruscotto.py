"""Cruscotto della lega: chi e' in regola e chi no, a colpo d'occhio.

Nessun conto si fa qui dentro. I numeri li produce `conformita.verifica_rosa`,
gli stessi che Streamlit mostra e che hanno i loro test: questo strato li
impacchetta in JSON e basta.

Il `momento` e' quello che cambia tutto: in stagione lo sforamento del Salary
Cap dovuto a uno scambio e' tollerato (art. 8b) e il Salary Floor non si
verifica; a fine asta tutto diventa vincolante. Chi guarda deve poter passare
da una lente all'altra, come fa oggi con l'interruttore in cima alla pagina.
"""

from __future__ import annotations

from fastapi import APIRouter, HTTPException
from pydantic import BaseModel

from fantacalcio.conformita import Momento, StatoRosa
from fantacalcio.data import calendario_dettagliato, carica_rose
from fantacalcio.mercato import stato_mercato
from fantacalcio.vista import stati_rose

from ..contesto import Contesto, contesto_di
from ..dipendenze import UtenteDentro

rotte = APIRouter(tags=["cruscotto"])

NON_ELABORABILE = 422


class Violazione(BaseModel):
    codice: str
    articolo: str
    gravita: str
    messaggio: str
    # Di quanto si sfora, non solo che si sfora: e' la regola del progetto, e
    # senza questi due numeri l'avviso non dice a nessuno cosa fare.
    valore: float | None
    limite: float | None
    bloccante: bool


class RigaCruscotto(BaseModel):
    squadra_id: int
    squadra: str
    dimensione: int
    limite_dimensione: int
    slot_u21: int
    portieri: int
    anni_impegnati: int
    monte_anni: int
    anni_disponibili: int
    contratti_annuali: int
    annuali_richiesti: int
    monte_ingaggi: float
    dead_money: float
    spesa_salariale: float
    limite_cap: float
    spazio_salariale: float
    conforme: bool
    violazioni: list[Violazione]


class Conteggio(BaseModel):
    """Un riquadro in cima alla pagina."""

    etichetta: str
    valore: str
    nota: str = ""
    # Da 0 a 1, quando ha senso disegnare una barra. None quando non ce l'ha.
    quota: float | None = None
    # "ok", "avviso", "male" oppure "" quando il dato e' neutro.
    stato: str = ""


class Cruscotto(BaseModel):
    momento: str
    momenti: list[dict[str, str]]
    conteggi: list[Conteggio]
    righe: list[RigaCruscotto]
    monte_anni: int
    salary_cap: float
    salary_floor: float
    mercato_bloccato: bool
    finestra_piu_recente: str


def _violazioni(stato: StatoRosa) -> list[Violazione]:
    return [
        Violazione(
            codice=v.codice,
            articolo=v.articolo,
            gravita=v.gravita.name,
            messaggio=v.messaggio,
            valore=v.valore,
            limite=v.limite,
            bloccante=v.bloccante,
        )
        for v in stato.violazioni
    ]


def _conteggi(
    ctx: Contesto, stati: dict[int, StatoRosa], giornate: int, mercato
) -> list[Conteggio]:
    previste = ctx.lega.opzioni.partecipanti if ctx.lega else len(stati)
    totali = ctx.calendario.giornate_totali
    non_conformi = [s for s in stati.values() if not s.conforme]
    ultima = mercato.finestra_piu_recente.value

    return [
        Conteggio(
            etichetta="Squadre",
            valore=str(len(stati)),
            nota=f"su {previste} previste" if ctx.lega else "",
            quota=len(stati) / max(previste, 1),
        ),
        Conteggio(
            etichetta="Giornate disputate",
            valore=str(giornate),
            nota=f"su {totali}",
            quota=giornate / max(totali, 1),
        ),
        Conteggio(
            etichetta="Rose non conformi",
            valore=str(len(non_conformi)),
            nota="tutto in regola" if not non_conformi else "da sistemare",
            stato="ok" if not non_conformi else "male",
        ),
        Conteggio(
            etichetta="Ultima finestra",
            # Il nome per esteso non ci sta nel riquadro.
            valore=ultima.replace("Finestra ", "").capitalize(),
            nota="mercato bloccato" if mercato.trade_deadline_superata else "aperta",
            stato="avviso" if mercato.trade_deadline_superata else "ok",
        ),
    ]


@rotte.get("/cruscotto", response_model=Cruscotto)
def cruscotto(utente: UtenteDentro, momento: str = Momento.STAGIONE.name) -> Cruscotto:
    try:
        lente = Momento[momento]
    except KeyError:
        raise HTTPException(
            status_code=NON_ELABORABILE, detail=f"Momento sconosciuto: {momento}"
        ) from None

    ctx = contesto_di(utente)
    rose = carica_rose(ctx.arch)
    stati = stati_rose(rose, ctx.riferimento_u21, ctx.parametri, lente)

    partite = calendario_dettagliato(ctx.arch)
    giocate = partite[partite["gol_casa"].notna()]
    giornate = int(giocate["giornata"].max()) if not giocate.empty else 0
    mercato = stato_mercato(giornate, ctx.calendario)

    righe = [
        RigaCruscotto(
            squadra_id=squadra_id,
            squadra=stato.squadra,
            dimensione=stato.dimensione,
            limite_dimensione=stato.limite_dimensione,
            slot_u21=stato.slot_u21,
            portieri=stato.portieri,
            anni_impegnati=stato.anni_impegnati,
            monte_anni=stato.monte_anni,
            anni_disponibili=stato.anni_disponibili,
            contratti_annuali=stato.contratti_annuali,
            annuali_richiesti=stato.annuali_richiesti,
            monte_ingaggi=stato.monte_ingaggi,
            dead_money=stato.dead_money,
            spesa_salariale=stato.spesa_salariale,
            limite_cap=stato.limite_cap,
            spazio_salariale=stato.spazio_salariale,
            conforme=stato.conforme,
            violazioni=_violazioni(stato),
        )
        for squadra_id, stato in stati.items()
    ]
    # Prima chi ha qualcosa da sistemare: e' la riga che si cerca entrando.
    righe.sort(key=lambda r: (r.conforme, r.squadra))

    return Cruscotto(
        momento=lente.name,
        momenti=[{"nome": m.name, "etichetta": m.value.capitalize()} for m in Momento],
        conteggi=_conteggi(ctx, stati, giornate, mercato),
        righe=righe,
        monte_anni=ctx.parametri.monte_anni,
        salary_cap=ctx.parametri.salary_cap,
        salary_floor=ctx.parametri.salary_floor,
        mercato_bloccato=mercato.trade_deadline_superata,
        finestra_piu_recente=mercato.finestra_piu_recente.value,
    )
