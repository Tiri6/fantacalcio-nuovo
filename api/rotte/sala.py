"""La sala del draft: dieci persone che guardano la stessa pagina.

**Si aggiorna interrogando, non con un canale aperto.** Per dieci persone un
giro ogni paio di secondi basta e avanza, e costa un ordine di grandezza meno
— in codice da mantenere e in cose che si rompono — di tenere dieci
connessioni vive dietro un proxy che le chiude quando gli pare.

Perche' interrogare non costi, la risposta porta una **versione**: l'impronta
di quel che la pagina mostra — quale sala, in che stato, quante chiamate. Chi
interroga manda quella che ha, e se non e' cambiato niente si risponde
`aggiornato: false` e basta, senza rileggere rose e listone. Non e' solo il
conto delle chiamate perche' non tutto cio' che cambia in sala e' una
chiamata: chi amministra apre e fa cominciare, e gli altri nove devono
vederlo senza ricaricare a mano.

**Chi chiama non sceglie il numero della chiamata.** Lo decide il registro
(`sala.registra`), e il database lo rifiuta se e' gia' preso: e' quello che
impedisce a due persone che premono nello stesso istante di prendere lo stesso
posto. Un controllo scritto qui non basterebbe, perche' fra il controllo e la
scrittura ci passa l'altra richiesta.
"""

from __future__ import annotations

from datetime import datetime

from fastapi import APIRouter, HTTPException, status
from pydantic import BaseModel, Field

from fantacalcio.competizioni import inizio_giornata
from fantacalcio.contratti import finestra_modifica_anni
from fantacalcio.data import (
    aggiorna_anni_chiamata,
    calendario_dettagliato,
    carica_chiamate,
    carica_giocatori,
    carica_rose,
    carica_sale,
    prossimo_id,
    salva_chiamata,
    salva_sala,
    svincolati,
)
from fantacalcio.draft import PESI_FASCIA, distribuzione_pick, sorteggia_lottery
from fantacalcio.sala import (
    Sala,
    SalaNonAmmessa,
    Scelta,
    StatoSala,
    TipoSala,
    Turno,
    apri,
    chiudi,
    comincia,
    registra,
    scelte_di,
    turni_successivi,
    turno,
    verifica_chiamata,
)
from fantacalcio.vista import classifica, contratti_in_scadenza

from ..contesto import DATA_DRAFT, Contesto, contesto_di
from ..dipendenze import UtenteDentro

rotte = APIRouter(tags=["sala"])

NON_ELABORABILE = 422

# Quante chiamate future si mostrano. Cinque e non tutte: in sala serve sapere
# se tocca fra poco, non leggere l'elenco di sessanta turni.
QUANTI_PROSSIMI = 5


# ---------------------------------------------------------------------------
# Quello che esce
# ---------------------------------------------------------------------------


class GiocatoreLibero(BaseModel):
    id: int
    nome: str
    club: str
    ruoli: list[str]
    ingaggio: float


class ChiamataLetta(BaseModel):
    numero: int
    squadra_id: int
    squadra: str
    giocatore_id: int
    giocatore: str
    ruoli: list[str]
    anni: int
    quando: str


class TurnoLetto(BaseModel):
    numero: int
    squadra_id: int
    squadra: str
    round: int
    posizione: int
    etichetta: str
    scade_il: str | None
    e_mio: bool


class ViolazioneLetta(BaseModel):
    codice: str
    articolo: str
    messaggio: str
    bloccante: bool


class PaginaSala(BaseModel):
    # L'impronta di quel che la pagina mostra: quale sala, in che stato,
    # quante chiamate. Chi interroga la rimanda, e se non e' cambiata si
    # risponde che non c'e' niente di nuovo.
    #
    # Non e' solo il numero delle chiamate perche' non tutto cio' che cambia
    # in sala e' una chiamata: chi amministra apre e fa cominciare, e gli
    # altri nove devono vederlo senza ricaricare la pagina a mano.
    versione: str
    aggiornato: bool = True

    c_e_una_sala: bool
    id: int | None
    tipo: str | None
    tipo_etichetta: str | None
    stato: str | None
    stagione: str | None
    chiamate_totali: int
    round_totali: int

    turno: TurnoLetto | None
    # Le chiamate che vengono dopo questa. In sala la domanda che tutti fanno
    # e' «dopo chi tocca?», e l'ordine e' congelato: si puo' rispondere.
    prossimi: list[TurnoLetto]
    chiamate: list[ChiamataLetta]
    disponibili: list[GiocatoreLibero]

    mia_squadra_id: int | None
    posso_amministrare: bool
    anni_minimo: int
    anni_massimo: int

    # Cosa ho preso io in questa sala, e se posso ancora correggerne gli anni.
    miei_acquisti: list[ChiamataLetta]
    anni_correggibili: bool
    anni_chiudono_il: str | None
    anni_motivo: str


class EsitoChiamata(BaseModel):
    fatta: bool
    messaggio: str
    violazioni: list[ViolazioneLetta]


# ---------------------------------------------------------------------------
# Traduzioni
# ---------------------------------------------------------------------------


def _sala_corrente(ctx: Contesto) -> Sala | None:
    """L'ultima sala della lega: aperta, in corso o appena chiusa.

    Una sola alla volta, perche' un draft alla volta e' quello che succede
    davvero: due sale aperte insieme vorrebbero dire due turni contemporanei
    sulla stessa rosa.
    """
    sale = carica_sale(ctx.arch, ctx.lega.id if ctx.lega else None)
    return sale[0] if sale else None


def _chiamata(scelta: Scelta, squadre: dict, giocatori: dict) -> ChiamataLetta:
    chi = giocatori.get(scelta.giocatore_id)
    return ChiamataLetta(
        numero=scelta.numero,
        squadra_id=scelta.squadra_id,
        squadra=squadre.get(scelta.squadra_id, str(scelta.squadra_id)),
        giocatore_id=scelta.giocatore_id,
        giocatore=chi.nome if chi else str(scelta.giocatore_id),
        ruoli=list(chi.ruoli) if chi else [],
        anni=scelta.anni,
        quando=scelta.quando,
    )


def _turno(atteso: Turno, squadre: dict, mia_squadra_id: int | None) -> TurnoLetto:
    return TurnoLetto(
        numero=atteso.numero,
        squadra_id=atteso.squadra_id,
        squadra=squadre.get(atteso.squadra_id, str(atteso.squadra_id)),
        round=atteso.round,
        posizione=atteso.posizione,
        etichetta=atteso.etichetta,
        scade_il=(
            atteso.scade_il.isoformat(timespec="seconds") if atteso.scade_il else None
        ),
        e_mio=atteso.squadra_id == mia_squadra_id,
    )


def _finestra(ctx: Contesto, sala: Sala | None):
    """Se gli anni degli acquisti si possono ancora correggere."""
    opzioni = ctx.lega.opzioni if ctx.lega else None
    if sala is None or sala.stato is not StatoSala.CHIUSA:
        return None
    if opzioni is not None and not opzioni.modifica_anni_dopo_draft:
        return None

    partite = calendario_dettagliato(ctx.arch)
    prossima = None
    if not partite.empty:
        giocate = partite[partite["gol_casa"].notna()]
        disputate = int(giocate["giornata"].max()) if not giocate.empty else 0
        prossima = inizio_giornata(partite, disputate + 1)

    chiusura = None
    if sala.chiusa_il:
        try:
            chiusura = datetime.fromisoformat(sala.chiusa_il)
        except ValueError:
            chiusura = None
    return finestra_modifica_anni(chiusura, prossima)


# ---------------------------------------------------------------------------
# La pagina
# ---------------------------------------------------------------------------


def _impronta(sala: Sala | None, quante_chiamate: int) -> str:
    if sala is None:
        return "nessuna"
    return f"{sala.id}-{sala.stato.value}-{quante_chiamate}"


@rotte.get("/sala", response_model=PaginaSala)
def pagina(utente: UtenteDentro, versione: str = "") -> PaginaSala:
    """Lo stato della sala.

    Con `versione` uguale all'impronta attuale, risponde che non c'e' niente
    di nuovo e non rilegge rose e listone.
    """
    ctx = contesto_di(utente)
    sala = _sala_corrente(ctx)
    amministra = bool(
        ctx.lega and (utente.id == ctx.lega.admin_id or utente.puo_importare)
    )

    vuota = PaginaSala(
        versione="nessuna",
        c_e_una_sala=False,
        id=None,
        tipo=None,
        tipo_etichetta=None,
        stato=None,
        stagione=None,
        chiamate_totali=0,
        round_totali=0,
        turno=None,
        prossimi=[],
        chiamate=[],
        disponibili=[],
        mia_squadra_id=utente.squadra_id,
        posso_amministrare=amministra,
        anni_minimo=ctx.parametri.contratto_anni_minimo,
        anni_massimo=ctx.parametri.contratto_anni_massimo,
        miei_acquisti=[],
        anni_correggibili=False,
        anni_chiudono_il=None,
        anni_motivo="",
    )
    if sala is None:
        return vuota.model_copy(update={"aggiornato": versione != "nessuna"})

    scelte = carica_chiamate(ctx.arch, sala.id)
    impronta = _impronta(sala, len(scelte))
    if versione == impronta:
        # Niente di nuovo: si risponde subito, senza rileggere rose e listone.
        return vuota.model_copy(update={"versione": impronta, "aggiornato": False})

    rose = carica_rose(ctx.arch)
    squadre = {id_: r.squadra.nome for id_, r in rose.items()}
    giocatori = carica_giocatori(ctx.arch)
    presi = {s.giocatore_id for s in scelte}
    liberi = svincolati(ctx.arch, giocatori) - presi

    attuale_turno = turno(sala, scelte)
    prossimi = turni_successivi(sala, scelte, QUANTI_PROSSIMI)
    miei = scelte_di(scelte, utente.squadra_id) if utente.squadra_id else []
    finestra = _finestra(ctx, sala)

    return PaginaSala(
        versione=impronta,
        c_e_una_sala=True,
        id=sala.id,
        tipo=sala.tipo.name,
        tipo_etichetta=sala.tipo.etichetta,
        stato=sala.stato.value,
        stagione=sala.stagione,
        chiamate_totali=sala.chiamate_totali,
        round_totali=sala.round_totali,
        turno=(
            _turno(attuale_turno, squadre, utente.squadra_id) if attuale_turno else None
        ),
        prossimi=[_turno(t, squadre, utente.squadra_id) for t in prossimi],
        chiamate=[_chiamata(s, squadre, giocatori) for s in reversed(scelte)],
        disponibili=sorted(
            (
                GiocatoreLibero(
                    id=g.id,
                    nome=g.nome,
                    club=g.club,
                    ruoli=list(g.ruoli),
                    ingaggio=g.ingaggio,
                )
                for gid, g in giocatori.items()
                if gid in liberi
            ),
            key=lambda g: -g.ingaggio,
        ),
        mia_squadra_id=utente.squadra_id,
        posso_amministrare=amministra,
        anni_minimo=ctx.parametri.contratto_anni_minimo,
        anni_massimo=ctx.parametri.contratto_anni_massimo,
        miei_acquisti=[_chiamata(s, squadre, giocatori) for s in miei],
        anni_correggibili=bool(finestra and finestra.aperta),
        anni_chiudono_il=(
            finestra.chiude_il.isoformat(timespec="seconds")
            if finestra and finestra.chiude_il
            else None
        ),
        anni_motivo=finestra.motivo if finestra else "",
    )


# ---------------------------------------------------------------------------
# Chiamare
# ---------------------------------------------------------------------------


class DaChiamare(BaseModel):
    giocatore_id: int
    anni: int = Field(ge=1)


@rotte.post("/sala/chiamate", response_model=EsitoChiamata)
def chiama(richiesta: DaChiamare, utente: UtenteDentro) -> EsitoChiamata:
    """Registra una chiamata, se e' il tuo turno e la rosa regge."""
    ctx = contesto_di(utente)
    sala = _sala_corrente(ctx)
    if sala is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND, detail="Non c'e' una sala aperta."
        )
    if utente.squadra_id is None:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Non hai una squadra in questa lega.",
        )

    rose = carica_rose(ctx.arch)
    rosa = rose.get(utente.squadra_id)
    if rosa is None:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Non hai una squadra in questa lega.",
        )

    giocatori = carica_giocatori(ctx.arch)
    chi = giocatori.get(richiesta.giocatore_id)
    if chi is None:
        raise HTTPException(
            status_code=NON_ELABORABILE, detail="Quel giocatore non esiste."
        )

    scelte = carica_chiamate(ctx.arch, sala.id)
    violazioni = verifica_chiamata(
        sala,
        scelte,
        utente.squadra_id,
        chi,
        richiesta.anni,
        rosa,
        svincolati(ctx.arch, giocatori),
        ctx.parametri,
        data_draft=DATA_DRAFT,
    )
    if violazioni:
        # Si torna 200 con le violazioni, non un errore: chi chiama deve
        # vedere **di quanto** sfora e poter correggere senza perdere la
        # pagina, con dieci persone che aspettano.
        return EsitoChiamata(
            fatta=False,
            messaggio="",
            violazioni=[
                ViolazioneLetta(
                    codice=v.codice,
                    articolo=v.articolo,
                    messaggio=v.messaggio,
                    bloccante=v.bloccante,
                )
                for v in violazioni
            ],
        )

    scelta = registra(sala, scelte, utente.squadra_id, chi.id, richiesta.anni)
    try:
        salva_chiamata(ctx.arch, sala.id, scelta)
    except Exception as errore:  # noqa: BLE001 - i backend alzano tipi diversi
        # Numero gia' preso: qualcun altro ha chiamato nello stesso istante.
        # Il database lo rifiuta, ed e' giusto cosi' — qui si traduce.
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail=("Qualcun altro ha chiamato in questo istante: ricarica e riprova."),
        ) from errore

    anni = "anno" if richiesta.anni == 1 else "anni"
    return EsitoChiamata(
        fatta=True,
        messaggio=f"{chi.nome} e' tuo, per {richiesta.anni} {anni}.",
        violazioni=[],
    )


# ---------------------------------------------------------------------------
# Correggere gli anni di quello che si e' preso
# ---------------------------------------------------------------------------


class DaCorreggere(BaseModel):
    giocatore_id: int
    anni: int = Field(ge=1)


@rotte.put("/sala/anni", response_model=EsitoChiamata)
def correggi_anni(richiesta: DaCorreggere, utente: UtenteDentro) -> EsitoChiamata:
    """Corregge gli anni di un giocatore **preso in questa sala**.

    Solo quelli: un giocatore che hai da due stagioni non si tocca, ed e'
    esattamente quello che l'articolo 8 protegge. La finestra si chiude col
    calcio d'inizio della giornata successiva.
    """
    ctx = contesto_di(utente)
    sala = _sala_corrente(ctx)
    if sala is None or utente.squadra_id is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND, detail="Non c'e' niente da correggere."
        )

    finestra = _finestra(ctx, sala)
    if finestra is None or not finestra.aperta:
        raise HTTPException(
            status_code=NON_ELABORABILE,
            detail=(
                finestra.motivo
                if finestra
                else "La finestra per correggere gli anni non e' aperta."
            ),
        )

    miei = {
        s.giocatore_id
        for s in scelte_di(carica_chiamate(ctx.arch, sala.id), utente.squadra_id)
    }
    if richiesta.giocatore_id not in miei:
        raise HTTPException(
            status_code=NON_ELABORABILE,
            detail="Si correggono solo gli anni dei giocatori presi in questa sala.",
        )

    minimo, massimo = (
        ctx.parametri.contratto_anni_minimo,
        ctx.parametri.contratto_anni_massimo,
    )
    if not minimo <= richiesta.anni <= massimo:
        raise HTTPException(
            status_code=NON_ELABORABILE,
            detail=(
                f"Contratto di {richiesta.anni} anni: ammessi da {minimo} a {massimo}."
            ),
        )

    aggiorna_anni_chiamata(
        ctx.arch, sala.id, utente.squadra_id, richiesta.giocatore_id, richiesta.anni
    )
    anni = "anno" if richiesta.anni == 1 else "anni"
    return EsitoChiamata(
        fatta=True,
        messaggio=f"Contratto portato a {richiesta.anni} {anni}.",
        violazioni=[],
    )


# ---------------------------------------------------------------------------
# La Lottery dell'articolo 3
# ---------------------------------------------------------------------------


class SquadraEstratta(BaseModel):
    squadra_id: int
    squadra: str
    # La fascia di partenza: «bassa» sono le peggio classificate, quelle che
    # si giocano le pick 1-5. Si mostra perche' spiega il risultato.
    fascia: str


class ProbabilitaPick(BaseModel):
    squadra: str
    # Per ogni pick, la probabilita' in percentuale. L'indice 0 e' la prima.
    per_pick: list[float]


class Lottery(BaseModel):
    ordine: list[SquadraEstratta]
    pesi: list[int]
    spiegazione: str
    # Quanto era probabile ogni pick, prima dell'estrazione. Si guarda **dopo**
    # per capire se e' uscita una sorpresa, ed e' il modo piu' onesto di
    # mostrare che la Lottery non e' un sorteggio.
    probabilita: list[ProbabilitaPick]


@rotte.post("/sala/lottery", response_model=Lottery)
def estrai_lottery(utente: UtenteDentro) -> Lottery:
    """Estrae l'ordine di chiamata come lo vuole l'articolo 3.

    **Non e' un mescolamento.** Sono due estrazioni distinte, una per fascia,
    con i pesi dell'articolo — alla peggio classificata della fascia spetta il
    50%, poi a scalare — e la seconda meta' della classifica si gioca le pick
    1-5. Mescolare a caso darebbe a tutti la stessa probabilita', che e'
    esattamente la cosa che la Lottery esiste per non fare.

    Non salva niente: l'ordine estratto si guarda, e poi si apre la sala con
    quello. Se la lega la Lottery la fa in altro modo — un'urna vera, una
    diretta — si trascrive e basta.
    """
    ctx = _solo_chi_amministra(utente)
    rose = carica_rose(ctx.arch)
    per_nome = {r.squadra.nome: id_ for id_, r in rose.items()}

    tabella = classifica(ctx.arch)
    nomi = [n for n in tabella["Squadra"] if n in per_nome] if not tabella.empty else []
    # Chi non ha ancora giocato non compare in classifica: si accoda, perche'
    # una squadra fuori dalla Lottery e' una squadra che non chiama mai.
    nomi += [r.squadra.nome for r in rose.values() if r.squadra.nome not in nomi]

    try:
        esito = sorteggia_lottery(nomi)
    except ValueError as errore:
        raise HTTPException(status_code=NON_ELABORABILE, detail=str(errore)) from errore

    # Diecimila simulazioni costano due decimi di secondo e si fanno una
    # volta per estrazione: le probabilita' delle pick dopo la prima
    # dipendono da chi e' gia' uscito, e in chiuso non si scrivono.
    stimate = distribuzione_pick(nomi, simulazioni=10_000)

    bassa = set(esito.fascia_bassa)
    return Lottery(
        ordine=[
            SquadraEstratta(
                squadra_id=per_nome[n],
                squadra=n,
                fascia="bassa" if n in bassa else "alta",
            )
            for n in esito.ordine
        ],
        pesi=list(PESI_FASCIA[: len(nomi) // 2]),
        spiegazione=(
            f"Due estrazioni distinte (art. 3): le pick 1-{len(nomi) // 2} fra "
            f"le ultime {len(nomi) // 2} classificate, le altre fra le prime. "
            f"Dentro ogni fascia la peggio classificata ha il peso piu' alto."
        ),
        probabilita=[
            ProbabilitaPick(
                squadra=nome,
                per_pick=[
                    round(stimate[nome].get(pick, 0.0) * 100, 1)
                    for pick in range(1, len(nomi) + 1)
                ],
            )
            for nome in nomi
        ],
    )


# ---------------------------------------------------------------------------
# Il tabellone, e la draft list dei contratti in scadenza
# ---------------------------------------------------------------------------


class RoundLetto(BaseModel):
    numero: int
    squadre: list[str]


class Tabellone(BaseModel):
    c_e_una_sala: bool
    tipo_etichetta: str
    round: list[RoundLetto]


@rotte.get("/sala/tabellone", response_model=Tabellone)
def tabellone(utente: UtenteDentro) -> Tabellone:
    """Tutti i round della sala aperta, uno sotto l'altro.

    «Quando richiamo?» e' la seconda domanda che fanno tutti, dopo «a chi
    tocca adesso»: l'ordine e' congelato all'apertura, quindi la risposta c'e'
    per intero e non solo per le prossime cinque chiamate.
    """
    ctx = contesto_di(utente)
    sala = _sala_corrente(ctx)
    if sala is None:
        return Tabellone(c_e_una_sala=False, tipo_etichetta="", round=[])

    rose = carica_rose(ctx.arch)
    nomi = {id_: r.squadra.nome for id_, r in rose.items()}
    quante = len(sala.squadre) or 1
    return Tabellone(
        c_e_una_sala=True,
        tipo_etichetta=sala.tipo.etichetta,
        round=[
            RoundLetto(
                numero=n + 1,
                squadre=[
                    nomi.get(s, str(s))
                    for s in sala.chiamate_previste[n * quante : (n + 1) * quante]
                ],
            )
            for n in range(sala.round_totali)
        ],
    )


class InScadenza(BaseModel):
    squadra: str
    giocatore: str
    club: str
    ruoli: str
    ingaggio: float


@rotte.get("/sala/scadenze", response_model=list[InScadenza])
def scadenze(utente: UtenteDentro) -> list[InScadenza]:
    """Chi arriva a scadenza naturale: la draft list della prossima asta.

    Non e' una previsione: sono i contratti annuali di adesso, cioe' chi
    rientra nel draft se nessuno lo rinnova.
    """
    ctx = contesto_di(utente)
    tabella = contratti_in_scadenza(carica_rose(ctx.arch))
    if tabella.empty:
        return []
    return [
        InScadenza(
            squadra=r["Squadra"],
            giocatore=r["Giocatore"],
            club=r["Club"],
            ruoli=r["Ruoli"],
            ingaggio=float(r["Ingaggio"]),
        )
        for _, r in tabella.iterrows()
    ]


# ---------------------------------------------------------------------------
# Aprire, cominciare, chiudere: di chi amministra
# ---------------------------------------------------------------------------


class DaAprire(BaseModel):
    tipo: str = "SETTEMBRE"
    round_totali: int = Field(ge=1, le=50)
    secondi_per_chiamata: int | None = None
    # L'ordine della Lottery, per squadra_id. Vuoto in riparazione, dove conta
    # solo la classifica.
    ordine_lottery: list[int] = []


def _solo_chi_amministra(utente) -> Contesto:
    ctx = contesto_di(utente)
    if not (ctx.lega and (utente.id == ctx.lega.admin_id or utente.puo_importare)):
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="La sala la apre chi amministra la lega.",
        )
    return ctx


@rotte.post("/sala", response_model=PaginaSala)
def apri_sala(richiesta: DaAprire, utente: UtenteDentro) -> PaginaSala:
    ctx = _solo_chi_amministra(utente)
    try:
        tipo = TipoSala[richiesta.tipo]
    except KeyError as errore:
        raise HTTPException(
            status_code=NON_ELABORABILE,
            detail=f"Tipo di sala sconosciuto: {richiesta.tipo}.",
        ) from errore

    esistente = _sala_corrente(ctx)
    if esistente is not None and esistente.stato is not StatoSala.CHIUSA:
        raise HTTPException(
            status_code=NON_ELABORABILE,
            detail=(
                f"C'e' gia' una sala {esistente.stato.value}: due sale insieme "
                f"vorrebbero dire due turni sulla stessa rosa."
            ),
        )

    rose = carica_rose(ctx.arch)
    tabella = classifica(ctx.arch)
    per_nome = {r.squadra.nome: id_ for id_, r in rose.items()}
    ordine_classifica = (
        [per_nome[n] for n in tabella["Squadra"] if n in per_nome]
        if not tabella.empty
        else sorted(rose)
    )
    # Chi non ha ancora giocato non compare in classifica: si accoda, cosi'
    # nessuna squadra resta fuori dal draft.
    ordine_classifica += [id_ for id_ in sorted(rose) if id_ not in ordine_classifica]

    lottery = [s for s in richiesta.ordine_lottery if s in rose]
    # Chi non e' stato estratto si accoda in ordine di classifica. Senza, un
    # ordine incompleto farebbe round piu' corti del numero di squadre, e
    # qualcuno non chiamerebbe mai: un ordine a meta' e' un errore di
    # trascrizione, non la volonta' di escludere una squadra.
    lottery += [s for s in ordine_classifica if s not in lottery]

    sala = apri(
        prossimo_id(ctx.arch, "sale"),
        ctx.lega.id if ctx.lega else None,
        tipo,
        ctx.stagione,
        richiesta.round_totali,
        lottery,
        ordine_classifica,
        secondi_per_chiamata=richiesta.secondi_per_chiamata,
    )
    salva_sala(ctx.arch, sala)
    return pagina(utente)


@rotte.post("/sala/comincia", response_model=PaginaSala)
def comincia_sala(utente: UtenteDentro) -> PaginaSala:
    ctx = _solo_chi_amministra(utente)
    sala = _sala_corrente(ctx)
    if sala is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Nessuna sala.")
    try:
        salva_sala(ctx.arch, comincia(sala))
    except SalaNonAmmessa as errore:
        raise HTTPException(status_code=NON_ELABORABILE, detail=str(errore)) from errore
    return pagina(utente)


@rotte.post("/sala/chiudi", response_model=PaginaSala)
def chiudi_sala(utente: UtenteDentro) -> PaginaSala:
    """Chiude la sala. Da qui si correggono gli anni, ma non si chiama piu'."""
    ctx = _solo_chi_amministra(utente)
    sala = _sala_corrente(ctx)
    if sala is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Nessuna sala.")
    try:
        salva_sala(ctx.arch, chiudi(sala))
    except SalaNonAmmessa as errore:
        raise HTTPException(status_code=NON_ELABORABILE, detail=str(errore)) from errore
    return pagina(utente)
