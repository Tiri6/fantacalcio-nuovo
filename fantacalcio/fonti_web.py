"""Le fonti pubbliche del listone, e come si consolidano in una lista sola.

Tre cose diverse, tre posti diversi da cui arrivano:

- **chi c'e'** (nome, squadra di Serie A, ruoli Mantra, quotazioni): il listone
  ufficiale di Fantacalcio.it, un `.xlsx` con un indirizzo stabile che cambia
  solo la stagione nel nome del file;
- **quanto prende**: Capology, che l'articolo 4 del regolamento indica come
  fonte degli stipendi lordi;
- **di dove e'** e **quando e' nato**: sempre Capology, che nella stessa
  tabella porta nazionalita' ed eta'.

Nessuna delle tre e' sotto il nostro controllo: un giorno cambieranno la
pagina senza avvisarci. Per questo qui dentro non c'e' un solo modo di
leggere, ma piu' tentativi in fila, e soprattutto **nessuna eccezione che
esce**: chi chiama riceve un `EsitoAggiornamento` che racconta cosa e'
riuscito e cosa no. Un aggiornamento a meta' — il listone si', gli stipendi
no — e' un risultato utile, non un fallimento: i nomi e i ruoli si aggiornano
lo stesso e gli ingaggi restano quelli di prima invece di azzerarsi.

Questo modulo non importa Streamlit: si puo' eseguire da riga di comando
(`python scripts/aggiorna_listone.py`) e si prova nei test senza rete.
"""

from __future__ import annotations

import json
import re
import unicodedata
from collections.abc import Callable, Iterable
from dataclasses import dataclass, field, replace
from datetime import date, datetime
from html.parser import HTMLParser

from .importazione import importa_listone, normalizza_nome_giocatore

# --- indirizzi --------------------------------------------------------------

MODELLO_URL_QUOTAZIONI = (
    "https://content.fantacalcio.it/statico/quotazioni/"
    "Quotazioni_Fantacalcio_Stagione_{stagione}.xlsx"
)
MODELLO_URL_CAPOLOGY = "https://www.capology.com/it/serie-a/salaries/{annata}/"

# Le pagine da cui, in un browser, si arriva ai due file: servono da Referer.
# Un CDN che difende i propri statici guarda **da dove arrivi**, non solo chi
# dici di essere, e a una richiesta senza provenienza risponde 403.
RIFERIMENTO_QUOTAZIONI = "https://www.fantacalcio.it/quotazioni-fantacalcio"
RIFERIMENTO_CAPOLOGY = "https://www.capology.com/it/"

# Ci si presenta come un browser. Non e' un trucco per entrare dove non si
# dovrebbe: sono file pubblici, scaricabili con un clic da chiunque. E' che
# una richiesta senza intestazioni non somiglia a nessun visitatore vero, e i
# filtri anti-abuso la trattano come tale.
INTESTAZIONI = {
    "User-Agent": (
        "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
        "(KHTML, like Gecko) Chrome/128.0.0.0 Safari/537.36"
    ),
    "Accept": (
        "text/html,application/xhtml+xml,application/xml;q=0.9,"
        "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet,"
        "image/avif,image/webp,*/*;q=0.8"
    ),
    "Accept-Language": "it-IT,it;q=0.9,en-US;q=0.8,en;q=0.7",
    "Accept-Encoding": "gzip, deflate",
    "Sec-Fetch-Dest": "document",
    "Sec-Fetch-Mode": "navigate",
    "Sec-Fetch-Site": "same-site",
    "Sec-Fetch-User": "?1",
    "Upgrade-Insecure-Requests": "1",
    "Connection": "keep-alive",
}

ATTESA_MASSIMA = 30  # secondi

# Fino a giugno si gioca ancora la stagione cominciata l'estate prima.
PRIMO_MESE_STAGIONE = 7


class FonteNonRaggiungibile(Exception):
    """La fonte non risponde, o risponde qualcosa che non e' quel che serve."""


Apri = Callable[[str], bytes]


def stagione(oggi: date | None = None) -> str:
    """Stagione in corso nella forma usata dal nome del file: `2026_27`."""
    oggi = oggi or date.today()
    inizio = oggi.year if oggi.month >= PRIMO_MESE_STAGIONE else oggi.year - 1
    return f"{inizio}_{(inizio + 1) % 100:02d}"


def annata(stagione_: str) -> str:
    """La stessa stagione come la scrive Capology: `2026-2027`."""
    inizio = int(stagione_.split("_")[0])
    return f"{inizio}-{inizio + 1}"


def etichetta_stagione(stagione_: str) -> str:
    inizio = int(stagione_.split("_")[0])
    return f"{inizio}/{(inizio + 1) % 100:02d}"


def url_quotazioni(stagione_: str) -> str:
    return MODELLO_URL_QUOTAZIONI.format(stagione=stagione_)


def url_capology(stagione_: str) -> str:
    return MODELLO_URL_CAPOLOGY.format(annata=annata(stagione_))


def riferimento_per(url: str) -> str:
    """La pagina da cui, in un browser, si arriverebbe a questo indirizzo."""
    from urllib.parse import urlparse

    dominio = urlparse(url).netloc.lower()
    if "fantacalcio.it" in dominio:
        return RIFERIMENTO_QUOTAZIONI
    if "capology.com" in dominio:
        return RIFERIMENTO_CAPOLOGY
    return ""


def scarica(url: str, attesa: int = ATTESA_MASSIMA, riferimento: str = "") -> bytes:
    """Una GET, con le intestazioni di un browser. L'unico punto che tocca la rete.

    `riferimento` diventa il Referer: e' la pagina da cui, cliccando, si
    arriverebbe a questo file. Senza, i CDN che proteggono gli statici
    rispondono 403 anche a un file pubblico. Se non lo si passa, si deduce dal
    dominio: cosi' chi chiama resta una funzione di un argomento solo, e i
    test possono sostituirla con qualsiasi cosa.
    """
    import gzip
    import urllib.error
    import urllib.request
    import zlib

    intestazioni = dict(INTESTAZIONI)
    riferimento = riferimento or riferimento_per(url)
    if riferimento:
        intestazioni["Referer"] = riferimento

    richiesta = urllib.request.Request(url, headers=intestazioni)
    try:
        with urllib.request.urlopen(richiesta, timeout=attesa) as risposta:
            grezzo = risposta.read()
            codifica = (risposta.headers.get("Content-Encoding") or "").lower()
    except urllib.error.HTTPError as errore:
        # Il messaggio dice anche *come* si e' chiesto. Serve a distinguere due
        # cose che a schermo sembrano identiche: un CDN che ci rifiuta davvero,
        # e un'applicazione che sta ancora girando sul codice di prima. Senza
        # questa coda, un 403 non permette di capire quale delle due sia.
        raise FonteNonRaggiungibile(
            f"{url} ha risposto {errore.code} ({errore.reason}) — chiesto con "
            f"intestazioni da browser"
            + (f" e Referer {riferimento}" if riferimento else " e nessun Referer")
        ) from errore
    except Exception as errore:  # noqa: BLE001 - urllib alza tipi eterogenei
        raise FonteNonRaggiungibile(f"{url} non risponde: {errore}") from errore

    # Chiediamo gzip come farebbe un browser, quindi tocca a noi scompattare:
    # urllib non lo fa da solo.
    try:
        if "gzip" in codifica:
            return gzip.decompress(grezzo)
        if "deflate" in codifica:
            return zlib.decompress(grezzo, -zlib.MAX_WBITS)
    except (OSError, zlib.error) as errore:
        raise FonteNonRaggiungibile(
            f"{url} ha risposto in {codifica} ma non si scompatta: {errore}"
        ) from errore
    return grezzo


# --- normalizzazione dei club ----------------------------------------------

# Parole che le due fonti mettono e tolgono a piacere: «Bologna FC 1909» e
# «Bologna» devono restare la stessa squadra.
_RUMORE_CLUB = {
    "fc",
    "ac",
    "as",
    "ss",
    "ssc",
    "us",
    "acf",
    "uc",
    "sc",
    "cfc",
    "bc",
    "calcio",
    "football",
    "club",
    "spa",
    "srl",
}

# Quel che il rumore non risolve: nomi proprio diversi per la stessa squadra.
ALIAS_CLUB = {
    "internazionale": "inter",
    "internazionalemilano": "inter",
    "hellasverona": "verona",
    "juve": "juventus",
    "napolissc": "napoli",
}


def normalizza_club(nome: str) -> str:
    senza_accenti = _senza_accenti(str(nome)).lower()
    parole = [p for p in re.split(r"[^a-z0-9]+", senza_accenti) if p]
    parole = [p for p in parole if p not in _RUMORE_CLUB and not p.isdigit()]
    chiave = "".join(parole)
    return ALIAS_CLUB.get(chiave, chiave)


def _senza_accenti(testo: str) -> str:
    return "".join(
        c for c in unicodedata.normalize("NFD", testo) if unicodedata.category(c) != "Mn"
    )


# --- Capology ---------------------------------------------------------------


@dataclass(frozen=True)
class Stipendio:
    """Una riga di Capology, ridotta a quel che serve al sito."""

    nome: str
    club: str
    lordo_annuo: float
    nazionalita: str = ""
    data_nascita: date | None = None
    eta: int | None = None


# Le chiavi cambiano nome fra una versione e l'altra del sito: si riconoscono
# per sinonimi invece che per posizione.
_SINONIMI = {
    "nome": ("player", "name", "playername", "giocatore", "nome"),
    "club": ("team", "club", "squadra", "teamname"),
    "lordo": (
        "grossannual",
        "annualgross",
        "grosssalary",
        "salarygross",
        "lordoannuale",
        "lordoannuo",
        "stipendiolordo",
        "grossy",
        "gross",
        "salary",
        "stipendio",
        "lordo",
        "ingaggio",
    ),
    "nazionalita": (
        "country",
        "nation",
        "nationality",
        "nazionalita",
        "nazione",
        "paese",
    ),
    "nascita": (
        "dob",
        "dateofbirth",
        "birthdate",
        "datadinascita",
        "datanascita",
        "nascita",
        "nato",
        "born",
    ),
    "eta": ("age", "eta"),
}


def _chiave(testo: str) -> str:
    return re.sub(r"[^a-z0-9]", "", _senza_accenti(str(testo)).lower())


def _mappa_campi(campi: Iterable[str]) -> dict[str, str]:
    """Da nome-del-campo-nella-fonte a nome nostro, per sinonimi."""
    normalizzati = {_chiave(c): c for c in campi}
    trovati: dict[str, str] = {}
    for nostro, sinonimi in _SINONIMI.items():
        for sinonimo in sinonimi:
            if sinonimo in normalizzati:
                trovati[nostro] = normalizzati[sinonimo]
                break
    return trovati


def leggi_importo(valore) -> float | None:
    """`€ 4.500.000`, `4,500,000`, `1.2M` → un numero. None se non lo e'."""
    if valore is None:
        return None
    if isinstance(valore, (int, float)):
        return float(valore)

    testo = _senza_accenti(str(valore)).strip()
    testo = re.sub(r"[€$£\s]", "", testo)
    if not testo:
        return None

    moltiplicatore = 1.0
    if testo[-1:].upper() in {"M", "K"}:
        moltiplicatore = 1_000_000.0 if testo[-1].upper() == "M" else 1_000.0
        testo = testo[:-1]

    # Separatori misti: si tiene per decimale solo l'ultimo separatore, e solo
    # se dietro ha una o due cifre. «4.500.000» sono quattro milioni e mezzo,
    # «4.5» sono quattro e mezzo.
    testo = testo.replace(",", ".")
    if "." in testo:
        testa, _, coda = testo.rpartition(".")
        testo = (
            f"{testa.replace('.', '')}.{coda}"
            if len(coda) <= 2
            else testo.replace(".", "")
        )

    try:
        return float(testo) * moltiplicatore
    except ValueError:
        return None


def _righe_da_json(testo: str) -> list[dict]:
    """Ogni array di oggetti JSON dentro la pagina che somigli alla tabella.

    Capology ha spostato i dati piu' volte: dentro `__NEXT_DATA__`, dentro un
    `var data = [...]`, dentro l'attributo di un tag. Invece di inseguire ogni
    versione si cercano tutti gli array di oggetti e si tiene il piu' lungo
    che abbia i campi giusti.
    """
    candidati: list[list[dict]] = []
    for inizio in (m.start() for m in re.finditer(r"\[\s*\{", testo)):
        blocco = _blocco_bilanciato(testo, inizio)
        if blocco is None:
            continue
        try:
            dati = json.loads(blocco)
        except ValueError:
            continue
        if isinstance(dati, list) and dati and isinstance(dati[0], dict):
            campi = _mappa_campi(dati[0].keys())
            if "nome" in campi and "lordo" in campi:
                candidati.append(dati)
    return max(candidati, key=len) if candidati else []


def _blocco_bilanciato(testo: str, inizio: int, massimo: int = 4_000_000) -> str | None:
    """Il testo da `[` alla sua parentesi di chiusura, saltando le stringhe."""
    profondita = 0
    in_stringa = False
    fuga = False
    for posizione in range(inizio, min(len(testo), inizio + massimo)):
        carattere = testo[posizione]
        if in_stringa:
            if fuga:
                fuga = False
            elif carattere == "\\":
                fuga = True
            elif carattere == '"':
                in_stringa = False
            continue
        if carattere == '"':
            in_stringa = True
        elif carattere in "[{":
            profondita += 1
        elif carattere in "]}":
            profondita -= 1
            if profondita == 0:
                return testo[inizio : posizione + 1]
    return None


class _LettoreTabella(HTMLParser):
    """Le tabelle HTML della pagina, come liste di righe di testo."""

    def __init__(self) -> None:
        super().__init__()
        self.tabelle: list[list[list[str]]] = []
        self._tabella: list[list[str]] | None = None
        self._riga: list[str] | None = None
        self._cella: list[str] | None = None

    def handle_starttag(self, tag, attrs):
        if tag == "table":
            self._tabella = []
        elif tag == "tr" and self._tabella is not None:
            self._riga = []
        elif tag in ("td", "th") and self._riga is not None:
            self._cella = []

    def handle_endtag(self, tag):
        if tag in ("td", "th") and self._cella is not None and self._riga is not None:
            self._riga.append(" ".join("".join(self._cella).split()))
            self._cella = None
        elif tag == "tr" and self._riga is not None and self._tabella is not None:
            if self._riga:
                self._tabella.append(self._riga)
            self._riga = None
        elif tag == "table" and self._tabella is not None:
            if self._tabella:
                self.tabelle.append(self._tabella)
            self._tabella = None

    def handle_data(self, dati):
        if self._cella is not None:
            self._cella.append(dati)


def _righe_da_tabella(testo: str) -> list[dict]:
    """Ripiego: la tabella HTML, con la prima riga per intestazione."""
    lettore = _LettoreTabella()
    try:
        lettore.feed(testo)
    except Exception:  # noqa: BLE001 - HTMLParser alza su markup rotto
        return []

    for tabella in sorted(lettore.tabelle, key=len, reverse=True):
        if len(tabella) < 2:
            continue
        intestazioni = tabella[0]
        campi = _mappa_campi(intestazioni)
        if "nome" not in campi or "lordo" not in campi:
            continue
        return [
            dict(zip(intestazioni, riga, strict=False))
            for riga in tabella[1:]
            if len(riga) == len(intestazioni)
        ]
    return []


def leggi_stipendi(pagina: bytes | str) -> list[Stipendio]:
    """Gli stipendi lordi annui da una pagina Capology, comunque siano scritti.

    Alza `FonteNonRaggiungibile` se la pagina non contiene niente di
    riconoscibile: e' un cambio di formato, e va detto invece che restituire
    una lista vuota che sembrerebbe «nessuno guadagna niente».
    """
    testo = pagina.decode("utf-8", "replace") if isinstance(pagina, bytes) else pagina

    grezze = _righe_da_json(testo) or _righe_da_tabella(testo)
    if not grezze:
        raise FonteNonRaggiungibile(
            "La pagina degli stipendi non contiene una tabella riconoscibile: "
            "il formato della fonte e' cambiato."
        )

    campi = _mappa_campi(grezze[0].keys())
    stipendi: list[Stipendio] = []
    for riga in grezze:
        nome = str(riga.get(campi.get("nome", ""), "")).strip()
        lordo = leggi_importo(riga.get(campi.get("lordo", "")))
        if not nome or lordo is None:
            continue
        eta = riga.get(campi.get("eta", ""))
        try:
            eta = int(float(eta)) if eta not in (None, "") else None
        except (TypeError, ValueError):
            eta = None
        stipendi.append(
            Stipendio(
                nome=nome,
                club=str(riga.get(campi.get("club", ""), "")).strip(),
                lordo_annuo=lordo,
                nazionalita=str(riga.get(campi.get("nazionalita", ""), "")).strip(),
                data_nascita=_leggi_data(riga.get(campi.get("nascita", ""))),
                eta=eta,
            )
        )

    if not stipendi:
        raise FonteNonRaggiungibile(
            "Tabella trovata ma nessuna riga leggibile: nomi o importi assenti."
        )
    return stipendi


def _separatore(testo: str) -> str:
    """Punto e virgola, virgola o tabulazione: si guarda la prima riga.

    La tabulazione c'e' perche' copiare una tabella da una pagina web e
    incollarla produce colonne separate da TAB: e' il modo piu' veloce di
    portare qui i dati di un sito che non offre l'esportazione.
    """
    prima = testo.splitlines()[0] if testo.splitlines() else ""
    conteggi = {carattere: prima.count(carattere) for carattere in ("\t", ";", ",")}
    migliore = max(conteggi, key=lambda c: conteggi[c])
    return migliore if conteggi[migliore] else ";"


def leggi_stipendi_incollati(contenuto: bytes | str) -> list[Stipendio]:
    """Gli stipendi da quel che si e' copiato da una pagina, comunque sia.

    Selezionare una tabella nel browser e premere Ctrl+C da colonne separate
    da TAB; copiare il sorgente da' HTML. Qui si accettano tutti e due, piu'
    il CSV di un foglio di calcolo, perche' chi incolla non deve sapere quale
    dei tre gli e' uscito.
    """
    testo = (
        contenuto.decode("utf-8-sig", "replace")
        if isinstance(contenuto, bytes)
        else contenuto
    )
    sembra_html = "<" in testo and ("<tr" in testo.lower() or "<table" in testo.lower())
    if sembra_html:
        try:
            return leggi_stipendi(testo)
        except FonteNonRaggiungibile:
            pass  # non era una tabella HTML leggibile: si prova come testo
    return leggi_stipendi_csv(testo)


def leggi_stipendi_csv(contenuto: bytes | str) -> list[Stipendio]:
    """Gli stipendi da un file scritto a mano, quando la fonte non si lascia leggere.

    Le colonne si riconoscono dal nome, in qualsiasi ordine e in italiano o in
    inglese: bastano `giocatore` e `lordo`. Separatore punto e virgola o
    virgola, come esce da Excel.
    """
    import csv
    import io

    testo = (
        contenuto.decode("utf-8-sig", "replace")
        if isinstance(contenuto, bytes)
        else contenuto
    )
    if not testo.strip():
        raise FonteNonRaggiungibile("Il file degli stipendi e' vuoto.")

    righe = list(csv.DictReader(io.StringIO(testo), delimiter=_separatore(testo)))
    if not righe:
        raise FonteNonRaggiungibile("Il file degli stipendi non ha righe.")

    campi = _mappa_campi(righe[0].keys())
    if "nome" not in campi or "lordo" not in campi:
        # Le intestazioni si stampano filtrando: se una riga ha piu' campi
        # dell'intestazione, DictReader mette `None` come chiave, e un join
        # su quella lista scoppierebbe proprio mentre si spiega l'errore.
        lette = ", ".join(c for c in righe[0] if isinstance(c, str) and c.strip())
        raise FonteNonRaggiungibile(
            "Nel file degli stipendi non trovo le colonne del giocatore e "
            f"dell'importo. Intestazioni lette: {lette or '(nessuna)'}."
        )

    stipendi = []
    for riga in righe:
        nome = str(riga.get(campi["nome"], "") or "").strip()
        lordo = leggi_importo(riga.get(campi["lordo"]))
        if not nome or lordo is None:
            continue
        stipendi.append(
            Stipendio(
                nome=nome,
                club=str(riga.get(campi.get("club", ""), "") or "").strip(),
                lordo_annuo=lordo,
                nazionalita=str(riga.get(campi.get("nazionalita", ""), "") or "").strip(),
                data_nascita=_leggi_data(riga.get(campi.get("nascita", ""))),
            )
        )

    if not stipendi:
        raise FonteNonRaggiungibile(
            "Nessuna riga leggibile: controlla che gli importi siano numeri."
        )
    return stipendi


MODELLO_CSV_STIPENDI = (
    "giocatore;squadra;lordo;nazionalita;nascita\n"
    "Paulo Dybala;Roma;6000000;Argentina;1993-11-15\n"
    "Nicolo Barella;Inter;9000000;Italia;1997-02-07\n"
)


# --- il listone tutto in un file --------------------------------------------
#
# Il modo piu' comodo di caricare a mano: un foglio solo con tutto dentro,
# invece dell'xlsx ufficiale piu' un file di stipendi a parte. Le colonne si
# riconoscono dal nome, in qualsiasi ordine.

_SINONIMI_LISTONE = {
    "id": ("id", "idgiocatore", "idufficiale", "idlistone", "playerid"),
    "nome": ("nome", "nomegiocatore", "giocatore", "player", "name"),
    "cognome": ("cognome", "cognomegiocatore", "surname", "lastname"),
    "club": (
        "squadradiprovenienza",
        "squadra",
        "club",
        "team",
        "squadraseriea",
    ),
    "classic": ("ruoloclassic", "ruoloclassico", "classic", "ruolo", "r"),
    "mantra": ("ruolomantra", "ruolimantra", "mantra", "rm", "ruoli"),
    "nascita": ("datadinascita", "datanascita", "nascita", "nato", "dob"),
    "nazionalita": ("nazionalita", "nazione", "paese", "country", "nationality"),
    "lordo": (
        "stipendiolordocapology",
        "stipendiolordo",
        "lordocapology",
        "stipendio",
        "lordo",
        "ingaggio",
        "grosssalary",
        "salary",
    ),
    "quotazione": ("quotazione", "qta", "qtam", "quota"),
    "fvm": ("fvm", "fvmm"),
}

COLONNE_LISTONE_CSV = (
    "id giocatore",
    "nome giocatore",
    "cognome giocatore",
    "squadra di provenienza",
    "ruolo classic",
    "ruolo mantra",
    "data di nascita",
    "nazionalita",
    "stipendio lordo",
)

MODELLO_CSV_LISTONE = (
    "id giocatore;nome giocatore;cognome giocatore;squadra di provenienza;"
    "ruolo classic;ruolo mantra;data di nascita;nazionalita;stipendio lordo\n"
    "2071;Paulo;Dybala;Roma;A;A/Pc;15/11/1993;Argentina;6000000\n"
    "555;Nicolo;Barella;Inter;C;M/C;07/02/1997;Italia;9000000\n"
)


def leggi_listone_csv(contenuto: bytes | str) -> list[RigaListone]:
    """Il listone completo da un unico foglio, come lo si prepara in Excel.

    Obbligatorie: **id giocatore**, **nome** (o cognome) e **ruolo mantra**.
    Tutto il resto e' facoltativo e, se manca, resta com'era in archivio.

    L'id e' obbligatorio perche' e' quel che tiene insieme le rose: i
    contratti puntano al giocatore, non al suo nome. Cambiare grafia a un nome
    non deve far perdere una rosa.
    """
    import csv
    import io

    from .importazione import leggi_ruoli

    testo = (
        contenuto.decode("utf-8-sig", "replace")
        if isinstance(contenuto, bytes)
        else contenuto
    )
    if not testo.strip():
        raise FonteNonRaggiungibile("Il file del listone e' vuoto.")

    grezze = list(csv.DictReader(io.StringIO(testo), delimiter=_separatore(testo)))
    if not grezze:
        raise FonteNonRaggiungibile(
            "Il file del listone non ha righe sotto l'intestazione — o non e' "
            f"un CSV. Colonne attese: {', '.join(COLONNE_LISTONE_CSV)}."
        )

    normalizzati = {_chiave(c): c for c in grezze[0] if c}
    campi: dict[str, str] = {}
    for nostro, sinonimi in _SINONIMI_LISTONE.items():
        for sinonimo in sinonimi:
            if sinonimo in normalizzati:
                campi[nostro] = normalizzati[sinonimo]
                break

    mancanti = [
        etichetta
        for chiave, etichetta in (("id", "id giocatore"), ("mantra", "ruolo mantra"))
        if chiave not in campi
    ]
    if "nome" not in campi and "cognome" not in campi:
        mancanti.append("nome giocatore")
    if mancanti:
        raise FonteNonRaggiungibile(
            f"Nel file mancano le colonne: {', '.join(mancanti)}. "
            f"Intestazioni lette: {', '.join(c for c in grezze[0] if c)}."
        )

    def campo(riga, chiave: str) -> str:
        colonna = campi.get(chiave)
        return str(riga.get(colonna, "") or "").strip() if colonna else ""

    righe: list[RigaListone] = []
    visti: set[int] = set()
    problemi: list[str] = []
    for numero, grezza in enumerate(grezze, start=2):
        nome = " ".join(x for x in (campo(grezza, "nome"), campo(grezza, "cognome")) if x)
        if not nome:
            continue
        try:
            identificativo = int(float(campo(grezza, "id")))
        except ValueError:
            problemi.append(f"riga {numero} ({nome}): id non numerico")
            continue
        if identificativo in visti:
            continue
        visti.add(identificativo)

        try:
            ruoli = leggi_ruoli(campo(grezza, "mantra"))
        except ValueError as errore:
            problemi.append(f"riga {numero} ({nome}): {errore}")
            continue

        righe.append(
            RigaListone(
                id_ufficiale=identificativo,
                nome=nome,
                club=campo(grezza, "club"),
                ruoli=ruoli,
                ruolo_classic=campo(grezza, "classic").upper(),
                quotazione=leggi_importo(campo(grezza, "quotazione")),
                fvm=leggi_importo(campo(grezza, "fvm")),
                ingaggio=leggi_importo(campo(grezza, "lordo")) or 0.0,
                nazionalita=campo(grezza, "nazionalita"),
                data_nascita=_leggi_data(campo(grezza, "nascita")),
            )
        )

    if not righe:
        dettaglio = f" Primi problemi: {'; '.join(problemi[:3])}." if problemi else ""
        raise FonteNonRaggiungibile(f"Nessuna riga leggibile nel file.{dettaglio}")
    return righe


def _leggi_data(valore) -> date | None:
    if valore in (None, ""):
        return None
    if isinstance(valore, date):
        return valore
    testo = str(valore).strip()[:10]
    for formato in ("%Y-%m-%d", "%d/%m/%Y", "%m/%d/%Y", "%d-%m-%Y"):
        try:
            return datetime.strptime(testo, formato).date()
        except ValueError:
            continue
    return None


# --- consolidamento ---------------------------------------------------------


@dataclass(frozen=True)
class RigaListone:
    """Una riga del file unico: listone e stipendi gia' messi insieme."""

    id_ufficiale: int
    nome: str
    club: str
    ruoli: tuple[str, ...]
    ruolo_classic: str = ""
    quotazione: float | None = None
    fvm: float | None = None
    ingaggio: float = 0.0
    nazionalita: str = ""
    data_nascita: date | None = None


@dataclass
class StatoFonte:
    nome: str
    url: str
    ok: bool
    dettaglio: str = ""


@dataclass
class EsitoAggiornamento:
    """Cosa e' arrivato, da dove, e cosa e' rimasto indietro."""

    righe: list[RigaListone] = field(default_factory=list)
    fonti: list[StatoFonte] = field(default_factory=list)
    senza_stipendio: list[str] = field(default_factory=list)
    stagione: str = ""
    quando: datetime | None = None

    @property
    def riuscito(self) -> bool:
        """Vero se almeno il listone e' arrivato: senza, non c'e' niente da scrivere."""
        return bool(self.righe)

    @property
    def con_stipendio(self) -> int:
        return sum(1 for r in self.righe if r.ingaggio > 0)


def _indicizza_stipendi(stipendi: Iterable[Stipendio]) -> dict:
    """Tre indici, dal piu' preciso al piu' generoso."""
    per_nome: dict[str, list[Stipendio]] = {}
    per_club: dict[str, list[Stipendio]] = {}
    for stipendio in stipendi:
        per_nome.setdefault(normalizza_nome_giocatore(stipendio.nome), []).append(
            stipendio
        )
        per_club.setdefault(normalizza_club(stipendio.club), []).append(stipendio)
    return {"per_nome": per_nome, "per_club": per_club}


def _parole(nome: str) -> list[str]:
    """Il nome ridotto a parole confrontabili: senza accenti, minuscole."""
    return [p for p in re.split(r"[^a-z0-9]+", _senza_accenti(str(nome)).lower()) if p]


def scomponi_nome_listone(nome: str) -> tuple[tuple[str, ...], str]:
    """Il cognome e l'iniziale, dal modo in cui scrive il listone.

    Fantacalcio.it distingue gli omonimi abbreviando il nome di battesimo:
    «Martinez Jo.» e «Martinez L.» sono Josep e Lautaro. L'ultima parola, se
    e' corta o finisce col punto, e' quell'abbreviazione e non un pezzo di
    cognome. Torna `(parole del cognome, iniziale)`.
    """
    parole = _parole(nome)
    if len(parole) >= 2 and len(parole[-1]) <= 3 and nome.strip().endswith("."):
        return tuple(parole[:-1]), parole[-1]
    return tuple(parole), ""


def _compatibile(candidato: Stipendio, cognome: tuple[str, ...], iniziale: str) -> bool:
    """Vero se il nome intero di Capology puo' essere quello del listone.

    Deve contenere **tutte** le parole del cognome come parole intere, e — se
    il listone abbreviava il nome di battesimo — un'altra parola che comincia
    per quell'abbreviazione. Il confronto per parole intere e' il punto: con
    il vecchio «e' contenuto dentro», «Martin» del Genoa si prendeva lo
    stipendio di «Josep Martinez» dell'Inter, perche' m-a-r-t-i-n sta dentro
    «martinez». Un ingaggio sbagliato in rosa costa piu' di uno mancante.
    """
    parole = _parole(candidato.nome)
    if not parole:
        return False
    # Il secondo confronto serve a chi ha il cognome staccato: il listone a
    # volte unisce quel che Capology separa («De Ketelaere»).
    if not set(cognome) <= set(parole) and "".join(cognome) != "".join(parole):
        return False
    if not iniziale:
        return True
    resto = [p for p in parole if p not in cognome]
    return any(p.startswith(iniziale) for p in resto)


def abbina(nome: str, club: str, indici: dict) -> Stipendio | None:
    """Trova la riga Capology di un giocatore del listone, o niente.

    Il listone scrive il cognome («Barella»), Capology il nome intero
    («Nicolo Barella»): l'uguaglianza secca non basta. Si prova, in ordine:
    nome identico; compatibile per parole intere dentro la stessa squadra;
    compatibile in tutta la lega, ma solo se e' uno solo.

    Un abbinamento ambiguo si scarta di proposito. Meglio uno stipendio che
    manca, e si vede nel rapporto, di uno sbagliato che entra in rosa zitto.
    """
    chiave = normalizza_nome_giocatore(nome)
    if not chiave:
        return None

    esatti = indici["per_nome"].get(chiave)
    if esatti:
        return esatti[0]

    cognome, iniziale = scomponi_nome_listone(nome)
    if not cognome:
        return None

    compagni = indici["per_club"].get(normalizza_club(club), [])
    candidati = [s for s in compagni if _compatibile(s, cognome, iniziale)]
    if len(candidati) == 1:
        return candidati[0]
    if candidati:
        return None  # due compagni di squadra plausibili: non si indovina

    ovunque = [
        s
        for lista in indici["per_nome"].values()
        for s in lista
        if _compatibile(s, cognome, iniziale)
    ]
    return ovunque[0] if len(ovunque) == 1 else None


def completa_ingaggi(
    righe: Iterable[RigaListone],
    ingaggi_correnti: dict[int, float] | None = None,
) -> tuple[list[RigaListone], list[str]]:
    """Tappa i buchi negli ingaggi con quel che si sapeva gia'.

    Serve al listone caricato in un file solo, che gli stipendi ce li ha gia'
    dentro: se una riga lo lascia a zero, meglio l'ingaggio della volta scorsa
    che nessun ingaggio.
    """
    correnti = ingaggi_correnti or {}
    complete: list[RigaListone] = []
    senza: list[str] = []
    for riga in righe:
        ingaggio = riga.ingaggio or float(correnti.get(riga.id_ufficiale, 0.0))
        if ingaggio <= 0:
            senza.append(f"{riga.nome} ({riga.club})")
        complete.append(
            riga if ingaggio == riga.ingaggio else replace(riga, ingaggio=ingaggio)
        )
    return complete, senza


def consolida(
    quotazioni: bytes,
    stipendi: Iterable[Stipendio] = (),
    ingaggi_correnti: dict[int, float] | None = None,
) -> tuple[list[RigaListone], list[str]]:
    """Listone + stipendi in una lista sola. Torna anche chi e' rimasto senza.

    `ingaggi_correnti` (per id ufficiale) tiene in piedi quel che si sapeva
    gia': se Capology non risponde per un giocatore, il suo ingaggio non
    diventa zero.
    """
    esito = importa_listone(quotazioni)
    if not esito.righe:
        messaggio = esito.problemi[0].messaggio if esito.problemi else "listone vuoto"
        raise FonteNonRaggiungibile(f"Listone non leggibile: {messaggio}")

    indici = _indicizza_stipendi(stipendi)
    correnti = ingaggi_correnti or {}
    righe: list[RigaListone] = []
    senza: list[str] = []

    for riga in esito.righe:
        trovato = (
            abbina(riga["nome"], riga["club"], indici) if indici["per_nome"] else None
        )
        if trovato is None:
            ingaggio = float(correnti.get(riga["id_ufficiale"], 0.0))
            if indici["per_nome"] and ingaggio <= 0:
                senza.append(f"{riga['nome']} ({riga['club']})")
        else:
            ingaggio = trovato.lordo_annuo

        righe.append(
            RigaListone(
                id_ufficiale=riga["id_ufficiale"],
                nome=riga["nome"],
                club=riga["club"],
                ruoli=riga["ruoli"],
                ruolo_classic=riga.get("ruolo_classic", ""),
                quotazione=riga["quotazione"],
                fvm=riga["fvm"],
                ingaggio=ingaggio,
                nazionalita=trovato.nazionalita if trovato else "",
                data_nascita=trovato.data_nascita if trovato else None,
            )
        )
    return righe, senza


def aggiorna_da_web(
    ingaggi_correnti: dict[int, float] | None = None,
    stagione_: str | None = None,
    apri: Apri = scarica,
    oggi: date | None = None,
    url_listone: str = "",
    url_stipendi: str = "",
) -> EsitoAggiornamento:
    """Scarica, legge e consolida. Non alza: racconta.

    `apri` e' iniettabile perche' i test non hanno rete e la rete non ha
    voglia di essere prevedibile. `url_listone` e `url_stipendi` servono a
    puntare altrove senza toccare il codice, il giorno che una delle due fonti
    cambia indirizzo o smette di lasciarsi leggere da un server.
    """
    stagione_ = stagione_ or stagione(oggi)
    esito = EsitoAggiornamento(stagione=stagione_, quando=datetime.now())

    indirizzo_listone = url_listone.strip() or url_quotazioni(stagione_)
    try:
        quotazioni = apri(indirizzo_listone)
    except FonteNonRaggiungibile as errore:
        esito.fonti.append(
            StatoFonte("Listone Fantacalcio.it", indirizzo_listone, False, str(errore))
        )
        return esito

    indirizzo_stipendi = url_stipendi.strip() or url_capology(stagione_)
    stipendi: list[Stipendio] = []
    try:
        stipendi = leggi_stipendi(apri(indirizzo_stipendi))
    except FonteNonRaggiungibile as errore:
        esito.fonti.append(
            StatoFonte("Stipendi Capology", indirizzo_stipendi, False, str(errore))
        )
    else:
        esito.fonti.append(
            StatoFonte(
                "Stipendi Capology",
                indirizzo_stipendi,
                True,
                f"{len(stipendi)} stipendi letti",
            )
        )

    try:
        righe, senza = consolida(quotazioni, stipendi, ingaggi_correnti)
    except FonteNonRaggiungibile as errore:
        esito.fonti.insert(
            0,
            StatoFonte("Listone Fantacalcio.it", indirizzo_listone, False, str(errore)),
        )
        return esito

    esito.fonti.insert(
        0,
        StatoFonte(
            "Listone Fantacalcio.it",
            indirizzo_listone,
            True,
            f"{len(righe)} giocatori letti",
        ),
    )
    esito.righe = righe
    esito.senza_stipendio = senza
    return esito


def aggiorna_da_file(
    quotazioni: bytes,
    stipendi_csv: bytes | str | None = None,
    ingaggi_correnti: dict[int, float] | None = None,
    stagione_: str | None = None,
    oggi: date | None = None,
) -> EsitoAggiornamento:
    """La stessa cosa, ma dai file che si sono scaricati a mano dal browser.

    Esiste perche' un browser, sulle stesse due pagine, entra sempre: ha i
    cookie, la cronologia e un indirizzo di casa. Un server no, e un CDN che
    lo rifiuta e' un problema che non si risolve dal nostro lato. Questa via
    non passa dalla rete, quindi non puo' fallire per colpa di nessuno.

    `quotazioni` accetta due cose: l'`.xlsx` ufficiale di Fantacalcio.it, o un
    CSV con tutto dentro (vedi `COLONNE_LISTONE_CSV`). Si riconoscono da soli:
    un xlsx e' uno zip, e comincia per `PK`.

    Il rapporto che torna e' lo stesso dell'aggiornamento automatico: chi
    guarda la pagina non deve imparare due linguaggi diversi.
    """
    esito = EsitoAggiornamento(
        stagione=stagione_ or stagione(oggi), quando=datetime.now()
    )

    # Un CSV porta gia' gli stipendi dentro: il file a parte non serve.
    if quotazioni[:2] != b"PK":
        try:
            righe = leggi_listone_csv(quotazioni)
        except FonteNonRaggiungibile as errore:
            esito.fonti.append(
                StatoFonte("Listone (CSV caricato)", "", False, str(errore))
            )
            return esito
        righe, senza = completa_ingaggi(righe, ingaggi_correnti)
        esito.fonti.append(
            StatoFonte(
                "Listone (CSV caricato)",
                "",
                True,
                f"{len(righe)} giocatori letti, "
                f"{sum(1 for r in righe if r.ingaggio > 0)} con lo stipendio",
            )
        )
        esito.righe = righe
        esito.senza_stipendio = senza
        return esito

    letti: list[Stipendio] = []
    if stipendi_csv:
        try:
            letti = leggi_stipendi_incollati(stipendi_csv)
        except FonteNonRaggiungibile as errore:
            esito.fonti.append(
                StatoFonte("Stipendi (file caricato)", "", False, str(errore))
            )
        else:
            esito.fonti.append(
                StatoFonte(
                    "Stipendi (file caricato)",
                    "",
                    True,
                    f"{len(letti)} stipendi letti",
                )
            )

    try:
        righe, senza = consolida(quotazioni, letti, ingaggi_correnti)
    except FonteNonRaggiungibile as errore:
        esito.fonti.insert(
            0, StatoFonte("Listone (file caricato)", "", False, str(errore))
        )
        return esito

    esito.fonti.insert(
        0,
        StatoFonte("Listone (file caricato)", "", True, f"{len(righe)} giocatori letti"),
    )
    esito.righe = righe
    esito.senza_stipendio = senza
    return esito


# --- il file unico ----------------------------------------------------------

COLONNE_CSV = (
    "id_ufficiale",
    "nome",
    "club",
    "ruolo_classic",
    "ruoli",
    "quotazione",
    "fvm",
    "ingaggio",
    "nazionalita",
    "data_nascita",
)


def a_csv(righe: Iterable[RigaListone]) -> str:
    """Il listone consolidato come un unico CSV, punto e virgola come sempre."""
    import csv
    import io

    buffer = io.StringIO()
    scrittore = csv.writer(buffer, delimiter=";", lineterminator="\n")
    scrittore.writerow(COLONNE_CSV)
    for riga in righe:
        scrittore.writerow(
            [
                riga.id_ufficiale,
                riga.nome,
                riga.club,
                riga.ruolo_classic,
                "/".join(riga.ruoli),
                "" if riga.quotazione is None else riga.quotazione,
                "" if riga.fvm is None else riga.fvm,
                f"{riga.ingaggio:.0f}",
                riga.nazionalita,
                riga.data_nascita.isoformat() if riga.data_nascita else "",
            ]
        )
    return buffer.getvalue()


def a_csv_da_completare(righe: Iterable[RigaListone]) -> str:
    """Il listone nel formato che il sito rilegge, con i buchi da riempire.

    Serve a chi ha il listone ufficiale ma non gli stipendi: si scarica questo,
    si riempiono a mano le tre colonne che mancano — stipendio lordo, data di
    nascita, nazionalita' — e lo si ricarica. Le colonne gia' note (id, nome,
    squadra, ruoli) restano dove sono, cosi' non si sbaglia l'abbinamento.
    """
    import csv
    import io

    buffer = io.StringIO()
    scrittore = csv.writer(buffer, delimiter=";", lineterminator="\n")
    scrittore.writerow(COLONNE_LISTONE_CSV)
    for riga in righe:
        scrittore.writerow(
            [
                riga.id_ufficiale,
                riga.nome,
                "",  # cognome: il listone tiene nome e cognome in un campo solo
                riga.club,
                riga.ruolo_classic,
                "/".join(riga.ruoli),
                riga.data_nascita.strftime("%d/%m/%Y") if riga.data_nascita else "",
                riga.nazionalita,
                f"{riga.ingaggio:.0f}" if riga.ingaggio else "",
            ]
        )
    return buffer.getvalue()


def a_righe_archivio(righe: Iterable[RigaListone], esistenti) -> list[dict]:
    """Le righe pronte per la tabella `giocatori`, conservando gli id interni.

    `esistenti` e' il DataFrame dei giocatori gia' in archivio: un giocatore
    gia' noto tiene il suo `id`, altrimenti i contratti punterebbero nel
    vuoto. Nazionalita' e data di nascita gia' presenti non si cancellano se
    la fonte questa volta non le porta.
    """
    per_ufficiale: dict[int, dict] = {}
    massimo = 0
    if esistenti is not None and not esistenti.empty:
        for _, r in esistenti.iterrows():
            massimo = max(massimo, int(r["id"]))
            ufficiale = r.get("id_ufficiale")
            if ufficiale is not None and str(ufficiale) not in ("", "nan"):
                try:
                    per_ufficiale[int(ufficiale)] = r.to_dict()
                except (TypeError, ValueError):
                    continue

    prossimo = massimo + 1
    fuori: list[dict] = []
    for riga in righe:
        precedente = per_ufficiale.get(riga.id_ufficiale)
        if precedente is None:
            identificativo = prossimo
            prossimo += 1
        else:
            identificativo = int(precedente["id"])

        nascita = riga.data_nascita.isoformat() if riga.data_nascita else None
        if nascita is None and precedente is not None:
            precedente_nascita = precedente.get("data_nascita")
            nascita = precedente_nascita if isinstance(precedente_nascita, str) else None

        nazionalita = riga.nazionalita or (
            str(precedente.get("nazionalita") or "") if precedente else ""
        )
        classic = riga.ruolo_classic or (
            str(precedente.get("ruolo_classic") or "") if precedente else ""
        )

        fuori.append(
            {
                "id": identificativo,
                "id_ufficiale": riga.id_ufficiale,
                "nome": riga.nome,
                "club": riga.club,
                "ruoli": ";".join(riga.ruoli),
                "ruolo_classic": classic,
                "ingaggio": float(riga.ingaggio),
                "nazionalita": nazionalita or "Italia",
                "data_nascita": nascita,
                "quotazione": riga.quotazione,
                "fvm": riga.fvm,
            }
        )
    return fuori


def applica(arch, righe: Iterable[RigaListone]) -> dict:
    """Scrive il listone consolidato in archivio. Torna un conteggio."""
    righe = list(righe)
    esistenti = arch.giocatori()
    da_scrivere = a_righe_archivio(righe, esistenti)

    # «Nuovi» sono quelli che in archivio non c'erano, non la differenza fra
    # due totali: caricare sei giocatori in un catalogo che ne ha cinquecento
    # non e' «meno cinque nuovi».
    gia_noti: set[int] = set()
    if esistenti is not None and not esistenti.empty:
        for valore in esistenti.get("id_ufficiale", []):
            try:
                gia_noti.add(int(valore))
            except (TypeError, ValueError):
                continue
    nuovi = sum(1 for r in da_scrivere if int(r["id_ufficiale"]) not in gia_noti)

    arch.scrivi("giocatori", da_scrivere, chiave="id")
    return {
        "totali": len(da_scrivere),
        "nuovi": nuovi,
        "con_stipendio": sum(1 for r in righe if r.ingaggio > 0),
    }
