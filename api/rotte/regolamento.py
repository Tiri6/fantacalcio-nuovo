"""Il regolamento applicato, e la chat che risponde a parole.

Due rotte per due domande diverse: «quanto vale questo parametro» si legge in
tabella, «posso mettere un difensore al posto di un attaccante» si chiede.

Le tabelle arrivano da `leghe.prospetto_regolamento`, la stessa che disegna la
pagina Streamlit. La chat legge il dossier di `assistente.scheda_regolamento`,
costruito scorrendo i campi dei parametri: **un parametro nuovo arriva da solo
in tutte e due**, e non c'e' un terzo posto dove i numeri possano divergere.

La risposta si manda **in streaming**, una riga JSON per pezzo. Una domanda di
regolamento ha una risposta breve ma il modello ci mette qualche secondo:
senza, la pagina resta muta e sembra rotta. Una riga per pezzo invece di testo
nudo perche' un guasto a meta' risposta deve restare distinguibile dalla
risposta — con il testo nudo, «la chiave e' stata rifiutata» arriverebbe nella
nuvoletta come se l'avesse detto il modello.
"""

from __future__ import annotations

import json
from collections.abc import Iterator

from fastapi import APIRouter, HTTPException, status
from fastapi.responses import StreamingResponse
from pydantic import BaseModel, Field

from fantacalcio import assistente
from fantacalcio.assistente import (
    AssistenteNonConfigurato,
    AssistenteNonRaggiungibile,
    DomandaNonValida,
    Messaggio,
)
from fantacalcio.config import leggi_secret
from fantacalcio.leghe import prospetto_regolamento
from fantacalcio.regole import ETICHETTE_RUOLO

from ..contesto import Contesto, contesto_di
from ..dipendenze import UtenteDentro

rotte = APIRouter(tags=["regolamento"])

NON_ELABORABILE = 422

DOMANDE_DI_ESEMPIO = (
    "Quanti contratti annuali mi servono con 32 giocatori in rosa?",
    "Chi puo' entrare al posto di un difensore centrale?",
    "Quanto mi costa svincolare un giocatore?",
    "A quanti punti scatta il primo gol?",
)


# ---------------------------------------------------------------------------
# Le tabelle
# ---------------------------------------------------------------------------


class VoceLetta(BaseModel):
    voce: str
    valore: str


class GruppoLetto(BaseModel):
    titolo: str
    nota: str
    voci: list[VoceLetta]


class Ruolo(BaseModel):
    sigla: str
    nome: str


class PaginaRegolamento(BaseModel):
    gruppi: list[GruppoLetto]
    ruoli_mantra: list[Ruolo]
    # Le due competizioni si raccontano a parole: sono righe di prosa, non
    # coppie voce/valore.
    coppa: str | None
    f1_rush: str | None
    chat_attiva: bool


@rotte.get("/regolamento", response_model=PaginaRegolamento)
def regolamento(utente: UtenteDentro) -> PaginaRegolamento:
    from fantacalcio.competizioni import giornate_f1_rush

    ctx = contesto_di(utente)
    if ctx.lega is None:
        raise HTTPException(
            status_code=NON_ELABORABILE, detail="Non sei dentro una lega."
        )
    opzioni = ctx.lega.opzioni

    coppa = None
    if opzioni.coppa_italia:
        regole = opzioni.regole_coppa
        coppa = (
            f"{regole.formato.etichetta}, {regole.squadre_ammesse} squadre "
            f"ammesse, primo turno alla {regole.prima_giornata}ª giornata e poi "
            f"uno ogni {regole.ogni_quante_giornate}. "
            + (
                "Teste di serie dalla classifica. "
                if regole.teste_di_serie
                else "Sorteggio libero. "
            )
            + (
                "A parita', passa chi ha piu' fantapunti."
                if regole.spareggio_ai_fantapunti
                else "A parita' si ripete la sfida."
            )
        )

    f1 = None
    if opzioni.f1_rush:
        regole_f1 = opzioni.regole_f1_rush
        turni = giornate_f1_rush(regole=regole_f1)
        f1 = (
            f"Ultime {regole_f1.giornate_serie_a} giornate di Serie A "
            f"({turni[0]}ª–{turni[-1]}ª). {regole_f1.criterio.etichetta}."
        )

    return PaginaRegolamento(
        gruppi=[
            GruppoLetto(
                titolo=g.titolo,
                nota=g.nota,
                voci=[VoceLetta(voce=v.voce, valore=v.valore) for v in g.voci],
            )
            for g in prospetto_regolamento(ctx.parametri, opzioni, ctx.riferimento_u21)
        ],
        ruoli_mantra=[
            Ruolo(sigla=sigla, nome=nome) for sigla, nome in ETICHETTE_RUOLO.items()
        ],
        coppa=coppa,
        f1_rush=f1,
        chat_attiva=bool(leggi_secret(assistente.CHIAVE_SECRET)),
    )


# ---------------------------------------------------------------------------
# La chat
# ---------------------------------------------------------------------------


class StatoChat(BaseModel):
    attiva: bool
    # La scheda si mostra a chi la vuole leggere: e' quello su cui la chat
    # risponde, e saperlo cambia le domande che si fanno.
    scheda: str
    domande_di_esempio: list[str]
    limite_domanda: int
    # Chi amministra puo' attivarla: a lui si spiega come, agli altri a chi
    # chiedere.
    posso_configurare: bool
    nome_secret: str


def _scheda(ctx: Contesto) -> str:
    if ctx.lega is None:
        raise HTTPException(
            status_code=NON_ELABORABILE, detail="Non sei dentro una lega."
        )
    return assistente.scheda_regolamento(
        ctx.parametri,
        ctx.lega.opzioni,
        nome_lega=ctx.lega.nome,
        data_u21=ctx.riferimento_u21,
        punti_aperti=assistente.punti_aperti_del_progetto(),
    )


@rotte.get("/regolamento/chat", response_model=StatoChat)
def stato_chat(utente: UtenteDentro) -> StatoChat:
    ctx = contesto_di(utente)
    return StatoChat(
        attiva=bool(leggi_secret(assistente.CHIAVE_SECRET)),
        scheda=_scheda(ctx),
        domande_di_esempio=list(DOMANDE_DI_ESEMPIO),
        limite_domanda=assistente.LIMITE_DOMANDA,
        posso_configurare=bool(
            ctx.lega and (utente.id == ctx.lega.admin_id or utente.puo_importare)
        ),
        nome_secret=assistente.CHIAVE_SECRET,
    )


class Domanda(BaseModel):
    testo: str = Field(min_length=1)
    # La conversazione la tiene il browser e la rimanda: il server non ha
    # sessioni di chat da conservare, scadere e ripulire, e due schede aperte
    # non si mescolano le risposte.
    storico: list[dict] = []


def _righe(pezzi: Iterator[str]) -> Iterator[bytes]:
    """Una riga JSON per pezzo, piu' una riga finale se qualcosa si rompe.

    Il guasto arriva **dentro** il flusso, quando lo stato HTTP e' gia' stato
    mandato: non si puo' piu' rispondere 422. Mandarlo come riga a parte e'
    l'unico modo perche' la pagina sappia che quello non e' il modello che
    parla.
    """
    try:
        for pezzo in pezzi:
            yield (json.dumps({"testo": pezzo}) + "\n").encode("utf-8")
    except AssistenteNonRaggiungibile as errore:
        yield (json.dumps({"errore": str(errore)}) + "\n").encode("utf-8")


@rotte.post("/regolamento/chat")
def chiedi(domanda: Domanda, utente: UtenteDentro) -> StreamingResponse:
    """Risponde alla domanda, un pezzo alla volta."""
    ctx = contesto_di(utente)
    chiave = leggi_secret(assistente.CHIAVE_SECRET)
    if not chiave:
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail=(
                f"Manca il secret {assistente.CHIAVE_SECRET}: la chat sul "
                f"regolamento e' spenta."
            ),
        )

    storico = [
        Messaggio(
            ruolo="utente" if m.get("ruolo") == "utente" else "assistente",
            testo=str(m.get("testo", "")),
        )
        for m in domanda.storico
    ]

    try:
        # `rispondi` valida la domanda **prima** di restituire il generatore:
        # cosi' una domanda vuota torna 422 invece di comparire nella
        # cronologia come se fosse stata fatta.
        pezzi = assistente.rispondi(
            domanda.testo, storico, _scheda(ctx), assistente.crea_client(chiave)
        )
    except DomandaNonValida as errore:
        raise HTTPException(status_code=NON_ELABORABILE, detail=str(errore)) from errore
    except AssistenteNonConfigurato as errore:
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE, detail=str(errore)
        ) from errore

    return StreamingResponse(
        _righe(pezzi),
        media_type="application/x-ndjson",
        # Senza, un proxy puo' accumulare la risposta e consegnarla tutta
        # insieme: lo streaming ci sarebbe ma non si vedrebbe.
        headers={"X-Accel-Buffering": "no", "Cache-Control": "no-store"},
    )
