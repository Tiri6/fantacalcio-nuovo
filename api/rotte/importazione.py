"""Caricare i dati della lega da file: listone, rose del draft, risultati.

Il flusso e' quello di Streamlit, e non per pigrizia: **prima l'anteprima,
poi la conferma**. Un import che scrive al primo clic, dopo un draft, vuol
dire dieci rose sbagliate e nessun modo di sapere quale riga le ha rotte.

Niente stato fra le due chiamate. L'anteprima non mette da parte l'esito per
la conferma: il file si rimanda, e si rilegge. Tenerlo in memoria del server
vorrebbe dire inventare scadenze, pulizie e un posto dove conservarlo —
mentre il file ce l'ha gia' il browser, e rileggerlo costa qualche
millisecondo. Soprattutto: la conferma valida di nuovo, quindi non esiste il
caso in cui si scrive un esito che nessuno ha piu' controllato.

Il file arriva in base64 dentro il JSON, come le immagini della maglia:
`python-multipart` non e' fra le dipendenze dell'API, e un formato di
trasporto in meno e' una cosa in meno che si rompe in produzione.

**Le regole non stanno qui.** Colonne, sinonimi, validazioni, conformita' e
scrittura sono tutte in `fantacalcio/importazione.py`, le stesse che usa
Streamlit. Qui si traduce.
"""

from __future__ import annotations

import base64

from fastapi import APIRouter, HTTPException, status
from pydantic import BaseModel

from fantacalcio.conformita import StatoRosa
from fantacalcio.data import carica_giocatori, svuota_listone
from fantacalcio.fonti_web import (
    MODELLO_CSV_LISTONE,
    EsitoAggiornamento,
    aggiorna_da_file,
)
from fantacalcio.fonti_web import applica as applica_catalogo
from fantacalcio.importazione import (
    CAMPI_LISTONE,
    CAMPI_RISULTATI,
    NOTA_FORMATO,
    CampoFile,
    EsitoImportazione,
    Problema,
    applica_risultati,
    applica_rose,
    campi_rose,
    catalogo_giocatori,
    importa_risultati,
    importa_rose,
    modello_risultati,
    modello_rose,
)

from ..contesto import DATA_DRAFT, Contesto, contesto_di
from ..dipendenze import UtenteDentro

rotte = APIRouter(tags=["importazione"])

NON_ELABORABILE = 422


# ---------------------------------------------------------------------------
# Quello che entra
# ---------------------------------------------------------------------------


class FileCaricato(BaseModel):
    """Il file, in base64. `nome` serve solo nei messaggi d'errore."""

    contenuto_base64: str
    nome: str = ""


class ListoneDaScrivere(FileCaricato):
    # Di partenza il file si **unisce** a quel che c'e': e' il modo giusto per
    # caricare gli stipendi un pezzo alla volta. Sostituire cancella chi non
    # compare nel file, e con lui il suo contratto — serve quando il file
    # precedente era sbagliato, non per un aggiornamento normale.
    sostituisci: bool = False


class RoseDaScrivere(FileCaricato):
    # Dopo un draft il file e' la situazione completa, quindi le rose
    # precedenti si azzerano: e' il caso normale, ed e' per questo che parte
    # da vero. Le squadre tengono id, nome e maglia.
    sostituisci: bool = True


# ---------------------------------------------------------------------------
# Quello che esce
# ---------------------------------------------------------------------------


class CampoLetto(BaseModel):
    nome: str
    obbligatorio: bool
    esempio: str
    nota: str


class ProblemaLetto(BaseModel):
    riga: int
    colonna: str
    valore: str
    messaggio: str


class Formati(BaseModel):
    """Cosa vogliono i tre file, piu' i modelli da scaricare."""

    posso_importare: bool
    giocatori_in_catalogo: int
    nota_formato: str
    campi_listone: list[CampoLetto]
    campi_rose: list[CampoLetto]
    campi_risultati: list[CampoLetto]
    modello_listone: str
    modello_rose: str
    modello_risultati: str
    soglia_primo_gol: float
    passo_gol: float


class ViolazioneLetta(BaseModel):
    codice: str
    articolo: str
    messaggio: str
    bloccante: bool


class StatoRosaLetto(BaseModel):
    squadra: str
    dimensione: int
    limite_dimensione: int
    slot_u21: int
    portieri: int
    anni_impegnati: int
    monte_anni: int
    contratti_annuali: int
    annuali_richiesti: int
    spesa_salariale: float
    limite_cap: float
    spazio_salariale: float
    conforme: bool
    violazioni: list[ViolazioneLetta]


class Esito(BaseModel):
    """L'anteprima, uguale per i tre file nelle parti che condividono."""

    lette: int
    errori: list[ProblemaLetto]
    avvisi: list[ProblemaLetto]
    intestazioni_ignorate: list[str]
    importabile: bool


class RigaRosa(BaseModel):
    riga: int
    squadra: str
    giocatore: str
    club: str
    ruoli: list[str]
    anni: int
    ingaggio: float


class EsitoRose(Esito):
    righe: list[RigaRosa]
    # Le rose sarebbero conformi? Si vede prima di scrivere, che e' il punto:
    # se il draft ha lasciato qualcuno fuori dai paletti si scopre adesso.
    squadre: list[StatoRosaLetto]


class RigaListone(BaseModel):
    id_ufficiale: int
    nome: str
    club: str
    ruoli: list[str]
    quotazione: float | None
    fvm: float | None
    # I tre che l'xlsx ufficiale non ha e il CSV si', ed e' tutta la ragione
    # per cui si accettano due formati: senza stipendio il Salary Cap e' a
    # zero, senza data di nascita lo status Under 21 non si puo' determinare.
    ingaggio: float
    nazionalita: str
    data_nascita: str | None


class EsitoListone(Esito):
    righe: list[RigaListone]
    club: int
    con_stipendio: int
    con_data_nascita: int
    con_nazionalita: int
    # Chi e' rimasto senza stipendio, per nome: e' la lista da controllare
    # prima di dare per buono un Salary Cap.
    senza_stipendio: list[str]
    # Cosa ha capito il lettore: «Listone (CSV caricato): 512 giocatori
    # letti, 498 con lo stipendio». Chi carica deve vedere che il file e'
    # stato riconosciuto per quel che e'.
    fonti: list[str]


class RigaRisultato(BaseModel):
    giornata: int
    casa: str
    trasferta: str
    punti_casa: float
    punti_trasferta: float


class EsitoRisultati(Esito):
    righe: list[RigaRisultato]


class Riepilogo(BaseModel):
    """Cosa e' stato scritto, in una frase che la pagina mostra com'e'."""

    messaggio: str


# ---------------------------------------------------------------------------
# Traduzioni
# ---------------------------------------------------------------------------


def _campo(campo: CampoFile) -> CampoLetto:
    return CampoLetto(
        nome=campo.nome,
        obbligatorio=campo.obbligatorio,
        esempio=campo.esempio,
        nota=campo.nota,
    )


def _problema(p: Problema) -> ProblemaLetto:
    return ProblemaLetto(
        riga=p.riga, colonna=p.colonna, valore=p.valore, messaggio=p.messaggio
    )


def _comuni(esito: EsitoImportazione) -> dict:
    return {
        "lette": len(esito.righe),
        "errori": [_problema(p) for p in esito.errori],
        "avvisi": [_problema(p) for p in esito.avvisi],
        "intestazioni_ignorate": list(esito.intestazioni_ignorate),
        "importabile": esito.importabile,
    }


def _stato(stato: StatoRosa) -> StatoRosaLetto:
    return StatoRosaLetto(
        squadra=stato.squadra,
        dimensione=stato.dimensione,
        limite_dimensione=stato.limite_dimensione,
        slot_u21=stato.slot_u21,
        portieri=stato.portieri,
        anni_impegnati=stato.anni_impegnati,
        monte_anni=stato.monte_anni,
        contratti_annuali=stato.contratti_annuali,
        annuali_richiesti=stato.annuali_richiesti,
        spesa_salariale=stato.spesa_salariale,
        limite_cap=stato.limite_cap,
        spazio_salariale=stato.spazio_salariale,
        conforme=stato.conforme,
        violazioni=[
            ViolazioneLetta(
                codice=v.codice,
                articolo=v.articolo,
                messaggio=v.messaggio,
                bloccante=v.bloccante,
            )
            for v in stato.violazioni
        ],
    )


# ---------------------------------------------------------------------------
# Permesso e lettura del file
# ---------------------------------------------------------------------------


def _solo_chi_importa(utente) -> Contesto:
    """L'import e' del presidente (art. 1), e lo dice il dominio.

    `puo_importare` e' la stessa proprieta' che in Streamlit decide se la
    pagina esiste. Qui non basta non mostrare il bottone: la rotta la si
    chiama anche a mano.
    """
    if not utente.puo_importare:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Solo il presidente puo' importare i dati della lega.",
        )
    return contesto_di(utente)


def _grezzo(caricato: FileCaricato) -> bytes:
    try:
        return base64.b64decode(caricato.contenuto_base64, validate=True)
    except Exception as errore:  # noqa: BLE001 - base64 alza tipi diversi
        raise HTTPException(
            status_code=NON_ELABORABILE,
            detail="Il file non e' leggibile: riprova a caricarlo.",
        ) from errore


# ---------------------------------------------------------------------------
# I formati
# ---------------------------------------------------------------------------


@rotte.get("/importazione", response_model=Formati)
def formati(utente: UtenteDentro) -> Formati:
    """Che file si possono caricare e cosa ci vuole dentro.

    Le colonne arrivano da `fantacalcio.importazione`: la pagina le mostra,
    non le sa. Con il listone gia' caricato «ruoli» e «club» risultano
    facoltativi, perche' e' esattamente la condizione che applica il lettore.
    """
    ctx = contesto_di(utente)
    catalogo = catalogo_giocatori(ctx.arch) if utente.puo_importare else {}
    return Formati(
        posso_importare=utente.puo_importare,
        giocatori_in_catalogo=len(catalogo),
        nota_formato=NOTA_FORMATO,
        campi_listone=[_campo(c) for c in CAMPI_LISTONE],
        campi_rose=[_campo(c) for c in campi_rose(con_catalogo=bool(catalogo))],
        campi_risultati=[_campo(c) for c in CAMPI_RISULTATI],
        modello_listone=MODELLO_CSV_LISTONE,
        modello_rose=modello_rose(),
        modello_risultati=modello_risultati(),
        soglia_primo_gol=ctx.parametri.soglia_primo_gol,
        passo_gol=ctx.parametri.passo_gol,
    )


# ---------------------------------------------------------------------------
# Listone
# ---------------------------------------------------------------------------


def _ingaggi_noti(ctx: Contesto) -> dict[int, float]:
    """Gli stipendi gia' in archivio, per id ufficiale.

    Si passano al lettore perche' l'xlsx ufficiale lo stipendio non ce l'ha:
    senza questa riga, ricaricare il listone azzererebbe tutti gli ingaggi
    inseriti a mano e il Salary Cap di tutti tornerebbe a zero.
    """
    return {
        g.id_ufficiale: g.ingaggio
        for g in carica_giocatori(ctx.arch).values()
        if g.id_ufficiale is not None and g.ingaggio
    }


def _leggi_listone(caricato: FileCaricato, ctx: Contesto) -> EsitoAggiornamento:
    """Legge il file, di qualunque dei due formati sia.

    Un solo lettore per tutti e due: il formato si riconosce dal contenuto (un
    xlsx e' uno zip, comincia per `PK`), non dal nome del file ne' da un
    pulsante diverso. Chi carica non deve sapere in che cassetto mettere il
    suo file — deve solo caricarlo.
    """
    return aggiorna_da_file(_grezzo(caricato), ingaggi_correnti=_ingaggi_noti(ctx))


def _esito_listone(esito: EsitoAggiornamento) -> EsitoListone:
    fallite = [f for f in esito.fonti if not f.ok]
    return EsitoListone(
        lette=len(esito.righe),
        errori=[
            ProblemaLetto(riga=0, colonna="file", valore="", messaggio=f.dettaglio)
            for f in fallite
        ],
        # Una riga scartata non ferma le altre: il file resta importabile, ma
        # chi carica deve vederle prima di scrivere.
        avvisi=[
            ProblemaLetto(riga=0, colonna="riga", valore="", messaggio=p)
            for p in esito.problemi
        ],
        intestazioni_ignorate=[],
        importabile=esito.riuscito,
        righe=[
            RigaListone(
                id_ufficiale=r.id_ufficiale,
                nome=r.nome,
                club=r.club,
                ruoli=list(r.ruoli),
                quotazione=r.quotazione,
                fvm=r.fvm,
                ingaggio=r.ingaggio,
                nazionalita=r.nazionalita,
                data_nascita=r.data_nascita.isoformat() if r.data_nascita else None,
            )
            for r in esito.righe
        ],
        club=len({r.club for r in esito.righe if r.club}),
        con_stipendio=esito.con_stipendio,
        con_data_nascita=sum(1 for r in esito.righe if r.data_nascita),
        con_nazionalita=sum(1 for r in esito.righe if r.nazionalita),
        senza_stipendio=list(esito.senza_stipendio),
        fonti=[
            f"{f.nome}: {f.dettaglio}" if f.dettaglio else f.nome for f in esito.fonti
        ],
    )


@rotte.post("/importazione/listone/anteprima", response_model=EsitoListone)
def anteprima_listone(caricato: FileCaricato, utente: UtenteDentro) -> EsitoListone:
    ctx = _solo_chi_importa(utente)
    return _esito_listone(_leggi_listone(caricato, ctx))


@rotte.post("/importazione/listone", response_model=Riepilogo)
def scrivi_listone(caricato: ListoneDaScrivere, utente: UtenteDentro) -> Riepilogo:
    """Scrive il catalogo. Chi c'e' gia' tiene ingaggio e contratto."""
    ctx = _solo_chi_importa(utente)
    esito = _leggi_listone(caricato, ctx)
    if not esito.riuscito:
        dettaglio = next(
            (f.dettaglio for f in esito.fonti if not f.ok), "file non leggibile"
        )
        raise HTTPException(status_code=NON_ELABORABILE, detail=dettaglio)

    riepilogo = applica_catalogo(ctx.arch, esito.righe, sostituisci=caricato.sostituisci)
    pezzi = [
        f"{riepilogo['totali']} giocatori nel catalogo",
        f"{riepilogo['nuovi']} nuovi",
        f"{riepilogo['con_stipendio']} con lo stipendio",
    ]
    if riepilogo["rimossi"]:
        pezzi.append(f"{riepilogo['rimossi']} cancellati")
    return Riepilogo(messaggio=f"{pezzi[0]} ({', '.join(pezzi[1:])}).")


# ---------------------------------------------------------------------------
# Rose
# ---------------------------------------------------------------------------


def _leggi_rose(caricato: FileCaricato, ctx: Contesto) -> EsitoImportazione:
    """Legge le rose col catalogo, se c'e': senza, servono ruoli e club."""
    catalogo = catalogo_giocatori(ctx.arch)
    return importa_rose(_grezzo(caricato), ctx.parametri, catalogo or None)


@rotte.post("/importazione/rose/anteprima", response_model=EsitoRose)
def anteprima_rose(caricato: FileCaricato, utente: UtenteDentro) -> EsitoRose:
    """L'anteprima, piu' la conformita' che ne risulterebbe squadra per squadra."""
    from fantacalcio.importazione import anteprima_conformita

    ctx = _solo_chi_importa(utente)
    esito = _leggi_rose(caricato, ctx)

    squadre: list[StatoRosaLetto] = []
    if esito.righe:
        stati = anteprima_conformita(esito, DATA_DRAFT, ctx.parametri)
        squadre = [_stato(stati[nome]) for nome in sorted(stati)]

    return EsitoRose(
        **_comuni(esito),
        righe=[
            RigaRosa(
                riga=r["riga_csv"],
                squadra=r["squadra"],
                giocatore=r["giocatore"],
                club=r["club"],
                ruoli=list(r["ruoli"]),
                anni=r["anni"],
                ingaggio=r["ingaggio"],
            )
            for r in esito.righe
        ],
        squadre=squadre,
    )


@rotte.post("/importazione/rose", response_model=Riepilogo)
def scrivi_rose(caricato: RoseDaScrivere, utente: UtenteDentro) -> Riepilogo:
    """Scrive le rose.

    Le violazioni **non** fermano la scrittura: una rosa fuori dai paletti
    dopo il draft e' una cosa che succede, e va sanata entro la chiusura del
    mercato — tenerla fuori dal sito non la sana, la nasconde. A fermare tutto
    sono gli errori di lettura, perche' quelli vorrebbero dire scrivere dati
    che nessuno ha letto.
    """
    ctx = _solo_chi_importa(utente)
    esito = _leggi_rose(caricato, ctx)
    try:
        riepilogo = applica_rose(ctx.arch, esito, sostituisci=caricato.sostituisci)
    except ValueError as errore:
        raise HTTPException(status_code=NON_ELABORABILE, detail=str(errore)) from errore
    return Riepilogo(
        messaggio=(
            f"Importati {riepilogo['giocatori']} giocatori e "
            f"{riepilogo['contratti']} contratti. "
            f"Squadre create: {riepilogo['squadre_create']}."
        )
    )


# ---------------------------------------------------------------------------
# Risultati
# ---------------------------------------------------------------------------


@rotte.post("/importazione/risultati/anteprima", response_model=EsitoRisultati)
def anteprima_risultati(caricato: FileCaricato, utente: UtenteDentro) -> EsitoRisultati:
    _solo_chi_importa(utente)
    esito = importa_risultati(_grezzo(caricato))
    return EsitoRisultati(
        **_comuni(esito),
        righe=[
            RigaRisultato(
                giornata=r["giornata"],
                casa=r["casa"],
                trasferta=r["trasferta"],
                punti_casa=r["punti_casa"],
                punti_trasferta=r["punti_trasferta"],
            )
            for r in esito.righe
        ],
    )


@rotte.post("/importazione/risultati", response_model=Riepilogo)
def scrivi_risultati(caricato: FileCaricato, utente: UtenteDentro) -> Riepilogo:
    """Scrive le partite. I gol li ricava dalle fasce della lega."""
    ctx = _solo_chi_importa(utente)
    esito = importa_risultati(_grezzo(caricato))
    try:
        riepilogo = applica_risultati(ctx.arch, esito)
    except ValueError as errore:
        # Due casi diversi, stesso tipo: errori ancora da correggere, o una
        # squadra del file che nella lega non esiste.
        raise HTTPException(status_code=NON_ELABORABILE, detail=str(errore)) from errore
    return Riepilogo(messaggio=f"Importate {riepilogo['partite']} partite.")


# ---------------------------------------------------------------------------
# Cancellare tutto il listone
# ---------------------------------------------------------------------------


class DaSvuotare(BaseModel):
    """La parola di conferma, scritta a mano.

    Non e' un fastidio inventato: cancellare il listone porta via **anche i
    contratti**, cioe' tutte le rose. Un bottone che lo fa al primo clic e'
    un bottone che prima o poi qualcuno preme per sbaglio.
    """

    conferma: str


class Svuotato(BaseModel):
    messaggio: str
    giocatori: int
    contratti: int


@rotte.post("/importazione/listone/svuota", response_model=Svuotato)
def svuota(richiesta: DaSvuotare, utente: UtenteDentro) -> Svuotato:
    """Cancella tutti i giocatori e tutti i contratti. Non si torna indietro.

    Per ricaricare un listone sbagliato **non serve**: basta caricare il file
    giusto con «sostituisci». Questo esiste per il caso in cui si vuole
    ripartire da zero davvero.
    """
    ctx = _solo_chi_importa(utente)
    if richiesta.conferma.strip().upper() != "CANCELLA":
        raise HTTPException(
            status_code=NON_ELABORABILE,
            detail="Scrivi CANCELLA per confermare: questa cancella anche le rose.",
        )

    andati = svuota_listone(ctx.arch)
    return Svuotato(
        messaggio=(
            f"Cancellati {andati['giocatori']} giocatori e "
            f"{andati['contratti']} contratti. Le squadre restano, le rose "
            f"sono vuote."
        ),
        giocatori=andati["giocatori"],
        contratti=andati["contratti"],
    )
