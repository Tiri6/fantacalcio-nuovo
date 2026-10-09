"""Le squadre della lega, con i conti che la pagina mostra in testa."""

from __future__ import annotations

from fastapi import APIRouter, HTTPException, status
from pydantic import BaseModel

from fantacalcio.competizioni import titoli_di
from fantacalcio.conformita import verifica_rosa
from fantacalcio.data import archivio, carica_albo, carica_rose

from ..contesto import contesto_di
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


class Violazione(BaseModel):
    codice: str
    articolo: str
    gravita: str
    messaggio: str
    # Di quanto sfora, non solo che sfora: e' la regola del progetto, e il
    # front-end non deve ricavarlo dal testo del messaggio.
    valore: float | None
    limite: float | None
    bloccante: bool


class GiocatoreInRosa(BaseModel):
    id: int
    nome: str
    club: str
    ruoli: list[str]
    nazionalita: str
    data_nascita: str | None
    eta: int | None
    italiano: bool
    u21: bool
    anni_residui: int
    ingaggio: float
    prolungato: bool
    in_scadenza: bool
    valore_residuo: float
    dead_money_se_tagliato: float


class Titolo(BaseModel):
    competizione: str
    etichetta: str
    icona: str
    stagione: str
    note: str


class Conti(BaseModel):
    giocatori: int
    limite_dimensione: int
    slot_u21: int
    portieri: int
    anni_impegnati: int
    monte_anni: int
    contratti_annuali: int
    annuali_richiesti: int
    monte_ingaggi: float
    dead_money: float
    limite_cap: float
    italiani: int
    u21: int


class SquadraInDettaglio(BaseModel):
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
    e_mia: bool
    posso_gestirla: bool
    conti: Conti
    rosa: list[GiocatoreInRosa]
    violazioni: list[Violazione]
    titoli: list[Titolo]
    riferimento_u21: str


@rotte.get("/squadre/{squadra_id}", response_model=SquadraInDettaglio)
def dettaglio(squadra_id: int, utente: UtenteDentro) -> SquadraInDettaglio:
    ctx = contesto_di(utente)
    rose = carica_rose(ctx.arch)
    rosa = rose.get(squadra_id)
    if rosa is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND, detail="Squadra inesistente."
        )

    s = rosa.squadra
    if utente.lega_id is not None and s.lega_id not in (None, utente.lega_id):
        # Una squadra di un'altra lega non e' «vietata», per chi guarda non
        # esiste proprio: dire «non puoi» confermerebbe che c'e'.
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND, detail="Squadra inesistente."
        )

    stato = verifica_rosa(rosa, ctx.riferimento_u21, ctx.parametri)

    giocatori = []
    for contratto in sorted(rosa.contratti, key=lambda c: -c.anni_residui):
        try:
            g = rosa.giocatore(contratto.giocatore_id)
        except KeyError:
            # Un contratto che punta a un giocatore fuori anagrafica: si salta,
            # come fa la pagina Streamlit, invece di far esplodere la rosa.
            continue
        residuo = contratto.valore_residuo(g.ingaggio)
        giocatori.append(
            GiocatoreInRosa(
                id=g.id,
                nome=g.nome,
                club=g.club,
                ruoli=list(g.ruoli),
                nazionalita=g.nazionalita,
                data_nascita=g.data_nascita.isoformat() if g.data_nascita else None,
                eta=g.eta_al(ctx.riferimento_u21),
                italiano=g.italiano,
                u21=g.under_21(ctx.riferimento_u21, ctx.parametri),
                anni_residui=contratto.anni_residui,
                ingaggio=g.ingaggio,
                prolungato=contratto.prolungato,
                in_scadenza=contratto.in_scadenza,
                valore_residuo=residuo,
                dead_money_se_tagliato=round(ctx.parametri.quota_dead_money * residuo, 2),
            )
        )

    titoli = titoli_di(
        carica_albo(ctx.arch, ctx.lega.id if ctx.lega else None), s.id, s.nome
    )

    i = s.identita
    return SquadraInDettaglio(
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
        e_mia=s.id == utente.squadra_id,
        posso_gestirla=utente.puo_gestire(s.id),
        conti=Conti(
            giocatori=stato.dimensione,
            limite_dimensione=stato.limite_dimensione,
            slot_u21=stato.slot_u21,
            portieri=stato.portieri,
            anni_impegnati=stato.anni_impegnati,
            monte_anni=ctx.parametri.monte_anni,
            contratti_annuali=stato.contratti_annuali,
            annuali_richiesti=stato.annuali_richiesti,
            monte_ingaggi=stato.monte_ingaggi,
            dead_money=stato.dead_money,
            limite_cap=stato.limite_cap,
            italiani=sum(1 for g in giocatori if g.italiano),
            u21=sum(1 for g in giocatori if g.u21),
        ),
        rosa=giocatori,
        violazioni=[
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
        ],
        titoli=[
            Titolo(
                competizione=t.competizione.name,
                etichetta=t.competizione.etichetta,
                icona=t.competizione.icona,
                stagione=t.stagione,
                note=t.note,
            )
            for t in titoli
        ],
        riferimento_u21=ctx.riferimento_u21.isoformat(),
    )
