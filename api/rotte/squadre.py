"""Le squadre della lega, con i conti che la pagina mostra in testa."""

from __future__ import annotations

from typing import Literal

from fastapi import APIRouter, HTTPException, status
from pydantic import BaseModel

from fantacalcio.competizioni import conta_per_competizione, titoli_di
from fantacalcio.conformita import Momento, verifica_rosa
from fantacalcio.data import (
    archivio,
    carica_albo,
    carica_giocatori,
    carica_rose,
    imposta_portiere_emergenza,
    registra_svincolo,
    svincolati,
)
from fantacalcio.emergenza import (
    EmergenzaNonAmmessa,
    malus_emergenza,
    stato_emergenza,
    verifica_attivazione,
    verifica_revoca,
)
from fantacalcio.mercato import (
    SvincoloNonAmmesso,
    calcola_dead_money,
    svincola,
    verifica_svincolo,
)

from ..contesto import contesto_di
from ..dipendenze import UtenteDentro

rotte = APIRouter(tags=["squadre"])

NON_ELABORABILE = 422


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


class ContoTitoli(BaseModel):
    """Quanti ne ha vinti, per competizione.

    Lo conta il dominio e non la pagina: contare le pastiglie a schermo
    funziona con tre titoli e smette di funzionare con venti.
    """

    etichetta: str
    icona: str
    quanti: int


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


class PortiereDellaRosa(BaseModel):
    id: int
    nome: str
    disponibile: bool


class PortiereLibero(BaseModel):
    """Un candidato: portiere, svincolato, con il suo ingaggio per confronto."""

    id: int
    nome: str
    club: str
    ingaggio: float


class Emergenza(BaseModel):
    """Lo stato del Lodo Messina per questa squadra.

    Arriva gia' deciso dal dominio: la pagina mostra `motivo` e abilita i
    bottoni secondo `ammessa` e `attiva`, senza rifare il ragionamento. Se lo
    rifacesse, la regola starebbe in due posti e il browser potrebbe dire una
    cosa e il server un'altra.
    """

    portieri: list[PortiereDellaRosa]
    attiva: bool
    ammessa: bool
    va_revocata: bool
    motivo: str
    in_carica_id: int | None
    in_carica_nome: str
    malus: float
    # Solo per chi puo' gestire la squadra: a chi guarda non serve l'elenco
    # dei portieri liberi della lega.
    candidati: list[PortiereLibero]


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
    titoli_per_competizione: list[ContoTitoli]
    riferimento_u21: str
    emergenza: Emergenza


def _emergenza(ctx, rosa, posso_gestirla: bool) -> Emergenza:
    """Il blocco emergenza di una squadra, con i candidati solo a chi la gestisce."""
    # L'anagrafica si legge **una volta**: e' tutto il listone, e qui servirebbe
    # tre volte (il portiere in carica, i candidati, gli svincolati).
    tutti = carica_giocatori(ctx.arch)

    nome_in_carica = ""
    if rosa.portiere_emergenza_id is not None:
        anagrafica = tutti.get(rosa.portiere_emergenza_id)
        nome_in_carica = anagrafica.nome if anagrafica else "?"

    stato = stato_emergenza(rosa, in_carica_nome=nome_in_carica)

    candidati: list[PortiereLibero] = []
    if posso_gestirla:
        candidati = sorted(
            (
                PortiereLibero(id=g.id, nome=g.nome, club=g.club, ingaggio=g.ingaggio)
                for gid in svincolati(ctx.arch, tutti)
                if (g := tutti.get(gid)) is not None and g.portiere
            ),
            key=lambda p: p.nome,
        )

    return Emergenza(
        portieri=[
            PortiereDellaRosa(id=p.id, nome=p.nome, disponibile=p.disponibile)
            for p in stato.portieri
        ],
        attiva=stato.attiva,
        ammessa=stato.ammessa,
        va_revocata=stato.va_revocata,
        motivo=stato.motivo,
        in_carica_id=stato.in_carica_id,
        in_carica_nome=stato.in_carica_nome,
        malus=malus_emergenza(ctx.parametri),
        candidati=candidati,
    )


def _rosa_gestibile(squadra_id: int, utente):
    """La rosa di una squadra che questo utente puo' gestire, o un errore.

    Il controllo sta qui e non nel browser: nascondere un bottone non e' un
    controllo, ed e' la regola del progetto.
    """
    ctx = contesto_di(utente)
    rosa = carica_rose(ctx.arch).get(squadra_id)
    if rosa is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND, detail="Squadra inesistente."
        )
    if utente.lega_id is not None and rosa.squadra.lega_id not in (
        None,
        utente.lega_id,
    ):
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND, detail="Squadra inesistente."
        )
    if not utente.puo_gestire(squadra_id):
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Il portiere d'emergenza lo attiva chi gestisce la squadra.",
        )
    return ctx, rosa


class Attivazione(BaseModel):
    giocatore_id: int
    # Quali portieri di ruolo la squadra dichiara indisponibili. Li dichiara
    # chi attiva: le indisponibilita' stanno su Leghe Fantacalcio, e questo
    # sito non le sa leggere da solo (vedi PUNTI_APERTI.md).
    indisponibili: list[int] = []


@rotte.post("/squadre/{squadra_id}/portiere-emergenza", response_model=Emergenza)
def attiva_emergenza(
    squadra_id: int, richiesta: Attivazione, utente: UtenteDentro
) -> Emergenza:
    """Attiva il portiere d'emergenza (art. 8, Lodo Messina)."""
    ctx, rosa = _rosa_gestibile(squadra_id, utente)

    tutti = carica_giocatori(ctx.arch)
    candidato = tutti.get(richiesta.giocatore_id)
    if candidato is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND, detail="Giocatore inesistente."
        )

    # Lo stato si valuta sulla dichiarazione **appena** arrivata, non su quella
    # salvata: e' quella che l'utente sta affermando adesso.
    stato = stato_emergenza(rosa, indisponibili=richiesta.indisponibili)
    try:
        verifica_attivazione(stato, candidato, svincolati(ctx.arch, tutti))
    except EmergenzaNonAmmessa as errore:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST, detail=str(errore)
        ) from errore

    imposta_portiere_emergenza(
        ctx.arch, squadra_id, candidato.id, richiesta.indisponibili
    )
    rosa.portiere_emergenza_id = candidato.id
    rosa.portieri_indisponibili = tuple(richiesta.indisponibili)
    return _emergenza(ctx, rosa, posso_gestirla=True)


@rotte.delete("/squadre/{squadra_id}/portiere-emergenza", response_model=Emergenza)
def revoca_emergenza(squadra_id: int, utente: UtenteDentro) -> Emergenza:
    """Revoca il portiere d'emergenza: torna disponibile uno di ruolo."""
    ctx, rosa = _rosa_gestibile(squadra_id, utente)

    try:
        verifica_revoca(stato_emergenza(rosa))
    except EmergenzaNonAmmessa as errore:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST, detail=str(errore)
        ) from errore

    imposta_portiere_emergenza(ctx.arch, squadra_id, None)
    rosa.portiere_emergenza_id = None
    rosa.portieri_indisponibili = ()
    return _emergenza(ctx, rosa, posso_gestirla=True)


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
                italiano=g.italiano,
                u21=g.under_21(),
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
        titoli_per_competizione=[
            ContoTitoli(etichetta=tipo.etichetta, icona=tipo.icona, quanti=quanti)
            for tipo, quanti in conta_per_competizione(titoli).items()
            if quanti
        ],
        riferimento_u21=ctx.riferimento_u21.isoformat(),
        emergenza=_emergenza(ctx, rosa, utente.puo_gestire(s.id)),
    )


# ---------------------------------------------------------------------------
# Svincolo (art. 7)
# ---------------------------------------------------------------------------
#
# Sta accanto alla rosa, non in una pagina a parte: e' da qui che si guarda chi
# c'e', e mandare a cercare altrove per togliere un giocatore che si ha davanti
# agli occhi e' il modo di far credere che non si possa.


class Svincolabile(BaseModel):
    """Un giocatore della rosa, col conto di cosa costa toglierlo.

    I numeri li fa il server con `mercato.calcola_dead_money`: la pagina li
    mostra e basta. Rifatti di la', sarebbero una seconda aritmetica del
    Lodo Origi, e la prima a sbagliare sarebbe quella che nessuno controlla.
    """

    giocatore_id: int
    nome: str
    anni_residui: int
    anni_oltre_quello_in_corso: int
    ingaggio: float
    valore_residuo: float
    dead_money: float
    a_carico_quest_anno: float


class Svincoli(BaseModel):
    posso_svincolare: bool
    quota_dead_money: float
    giocatori: list[Svincolabile]


class DaSvincolare(BaseModel):
    giocatore_id: int
    # Tre casi e non due: il V3 distingue **quando** si svincola. Prima
    # dell'asta di Settembre non c'e' nessun effetto sul Salary Cap; in
    # riparazione ci sono buonuscita e ingaggio a carico; la correzione di
    # un'assegnazione sbagliata non addebita niente, perche' un contratto messo
    # per errore non ha prodotto valore residuo.
    motivo: Literal["riparazione", "pre-asta", "correzione"] = "riparazione"


class SvincoloFatto(BaseModel):
    messaggio: str
    anni_liberati: int
    dead_money: float


def _svincolabili(ctx, rosa) -> list[Svincolabile]:
    voci: list[Svincolabile] = []
    for contratto in sorted(rosa.contratti, key=lambda c: -c.anni_residui):
        try:
            chi = rosa.giocatore(contratto.giocatore_id)
        except KeyError:
            # Contratto che punta a un giocatore fuori anagrafica: non si
            # svincola quello che non si sa nemmeno nominare.
            continue
        dovuto = calcola_dead_money(contratto, chi.ingaggio, ctx.parametri)
        voci.append(
            Svincolabile(
                giocatore_id=chi.id,
                nome=chi.nome,
                anni_residui=contratto.anni_residui,
                anni_oltre_quello_in_corso=contratto.anni_oltre_quello_in_corso,
                ingaggio=chi.ingaggio,
                valore_residuo=contratto.valore_residuo(chi.ingaggio),
                dead_money=dovuto,
                a_carico_quest_anno=dovuto + chi.ingaggio,
            )
        )
    return voci


@rotte.get("/squadre/{squadra_id}/svincoli", response_model=Svincoli)
def svincolabili(squadra_id: int, utente: UtenteDentro) -> Svincoli:
    """Chi si puo' togliere da questa rosa, e quanto costa."""
    ctx = contesto_di(utente)
    rosa = carica_rose(ctx.arch).get(squadra_id)
    if rosa is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND, detail="Squadra inesistente."
        )
    return Svincoli(
        posso_svincolare=utente.puo_svincolare,
        quota_dead_money=ctx.parametri.quota_dead_money,
        giocatori=_svincolabili(ctx, rosa) if utente.puo_svincolare else [],
    )


@rotte.post("/squadre/{squadra_id}/svincoli", response_model=SvincoloFatto)
def svincola_giocatore(
    squadra_id: int, richiesta: DaSvincolare, utente: UtenteDentro
) -> SvincoloFatto:
    """Toglie un giocatore dalla rosa, con l'effetto che il motivo comporta.

    Il permesso lo controlla `mercato.verifica_svincolo`, che e' del dominio:
    e' del presidente anche sulla propria squadra. Che questa rotta ci sia o no
    non e' il controllo, e' la conseguenza.
    """
    ctx = contesto_di(utente)
    rosa = carica_rose(ctx.arch).get(squadra_id)
    if rosa is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND, detail="Squadra inesistente."
        )

    contratto = rosa.contratto_di(richiesta.giocatore_id)
    if contratto is None:
        raise HTTPException(
            status_code=NON_ELABORABILE,
            detail=f"{rosa.squadra.nome} non ha in rosa quel giocatore.",
        )

    try:
        verifica_svincolo(utente, rosa, richiesta.giocatore_id)
    except SvincoloNonAmmesso as errore:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN, detail=str(errore)
        ) from errore

    voce = None
    if richiesta.motivo != "correzione":
        _, voce = svincola(
            rosa,
            richiesta.giocatore_id,
            ctx.stagione,
            ctx.parametri,
            momento=(
                Momento.RIPARAZIONE
                if richiesta.motivo == "riparazione"
                else Momento.ASTA_SETTEMBRE
            ),
        )

    registra_svincolo(ctx.arch, squadra_id, richiesta.giocatore_id, voce)

    nome = rosa.giocatore(richiesta.giocatore_id).nome
    anni = "anno" if contratto.anni_residui == 1 else "anni"
    messaggio = (
        f"{nome} e' tornato svincolato: {contratto.anni_residui} {anni} "
        f"tornano liberi nel monte di {rosa.squadra.nome}."
    )
    if voce is not None and voce.importo:
        messaggio += f" Dead Money addebitato: {voce.importo / 1_000_000:.2f}M."
    return SvincoloFatto(
        messaggio=messaggio,
        anni_liberati=contratto.anni_residui,
        dead_money=voce.importo if voce else 0.0,
    )
