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
from fantacalcio.importazione import (
    CAMPI_LISTONE,
    CAMPI_RISULTATI,
    NOTA_FORMATO,
    CampoFile,
    EsitoImportazione,
    Problema,
    applica_listone,
    applica_risultati,
    applica_rose,
    campi_rose,
    catalogo_giocatori,
    importa_listone,
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


class EsitoListone(Esito):
    righe: list[RigaListone]
    club: int


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
        modello_rose=modello_rose(),
        modello_risultati=modello_risultati(),
        soglia_primo_gol=ctx.parametri.soglia_primo_gol,
        passo_gol=ctx.parametri.passo_gol,
    )


# ---------------------------------------------------------------------------
# Listone
# ---------------------------------------------------------------------------


def _leggi_listone(caricato: FileCaricato) -> EsitoImportazione:
    return importa_listone(_grezzo(caricato))


def _esito_listone(esito: EsitoImportazione) -> EsitoListone:
    return EsitoListone(
        **_comuni(esito),
        righe=[
            RigaListone(
                id_ufficiale=r["id_ufficiale"],
                nome=r["nome"],
                club=r["club"],
                ruoli=list(r["ruoli"]),
                quotazione=r["quotazione"],
                fvm=r["fvm"],
            )
            for r in esito.righe
        ],
        club=len({r["club"] for r in esito.righe if r["club"]}),
    )


@rotte.post("/importazione/listone/anteprima", response_model=EsitoListone)
def anteprima_listone(caricato: FileCaricato, utente: UtenteDentro) -> EsitoListone:
    _solo_chi_importa(utente)
    return _esito_listone(_leggi_listone(caricato))


@rotte.post("/importazione/listone", response_model=Riepilogo)
def scrivi_listone(caricato: FileCaricato, utente: UtenteDentro) -> Riepilogo:
    """Scrive il catalogo. Chi c'e' gia' tiene ingaggio e contratto."""
    ctx = _solo_chi_importa(utente)
    esito = _leggi_listone(caricato)
    if not esito.importabile:
        raise HTTPException(
            status_code=NON_ELABORABILE,
            detail=f"{len(esito.errori)} errori da correggere prima di importare.",
        )
    riepilogo = applica_listone(ctx.arch, esito)
    return Riepilogo(
        messaggio=(
            f"{riepilogo['totali']} giocatori nel catalogo "
            f"({riepilogo['nuovi']} nuovi, {riepilogo['aggiornati']} aggiornati)."
        )
    )


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
