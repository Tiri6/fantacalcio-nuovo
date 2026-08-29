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
from dataclasses import dataclass, field
from datetime import date, datetime
from html.parser import HTMLParser

from .importazione import importa_listone, normalizza_nome_giocatore

# --- indirizzi --------------------------------------------------------------

MODELLO_URL_QUOTAZIONI = (
    "https://content.fantacalcio.it/statico/quotazioni/"
    "Quotazioni_Fantacalcio_Stagione_{stagione}.xlsx"
)
MODELLO_URL_CAPOLOGY = "https://www.capology.com/it/serie-a/salaries/{annata}/"

# Ci si presenta come un browser: senza User-Agent parecchi CDN rispondono 403.
INTESTAZIONI = {
    "User-Agent": (
        "Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36 "
        "(KHTML, like Gecko) Chrome/126.0 Safari/537.36"
    ),
    "Accept-Language": "it-IT,it;q=0.9",
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


def scarica(url: str, attesa: int = ATTESA_MASSIMA) -> bytes:
    """Una GET e basta. Isolata qui perche' e' l'unico punto che tocca la rete."""
    import urllib.error
    import urllib.request

    richiesta = urllib.request.Request(url, headers=INTESTAZIONI)
    try:
        with urllib.request.urlopen(richiesta, timeout=attesa) as risposta:
            return risposta.read()
    except urllib.error.HTTPError as errore:
        raise FonteNonRaggiungibile(
            f"{url} ha risposto {errore.code} ({errore.reason})"
        ) from errore
    except Exception as errore:  # noqa: BLE001 - urllib alza tipi eterogenei
        raise FonteNonRaggiungibile(f"{url} non risponde: {errore}") from errore


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
        "grossy",
        "gross",
        "salary",
        "stipendio",
    ),
    "nazionalita": ("country", "nation", "nationality", "nazionalita", "paese"),
    "nascita": ("dob", "dateofbirth", "birthdate", "datanascita", "born"),
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


def abbina(nome: str, club: str, indici: dict) -> Stipendio | None:
    """Trova la riga Capology di un giocatore del listone, o niente.

    Il listone scrive il cognome («Barella»), Capology il nome intero
    («Nicolo Barella»): l'uguaglianza secca non basta. Si prova, in ordine:
    nome identico; contenuto dentro un nome della stessa squadra, se e' uno
    solo; contenuto in un nome qualsiasi, se e' uno solo in tutta la lega.
    Un abbinamento ambiguo si scarta: un ingaggio sbagliato in rosa costa piu'
    di un ingaggio mancante, che almeno si vede.
    """
    chiave = normalizza_nome_giocatore(nome)
    if not chiave:
        return None

    esatti = indici["per_nome"].get(chiave)
    if esatti:
        return esatti[0]

    compagni = indici["per_club"].get(normalizza_club(club), [])
    candidati = [s for s in compagni if chiave in normalizza_nome_giocatore(s.nome)]
    if len(candidati) == 1:
        return candidati[0]

    if len(chiave) >= 5:
        ovunque = [
            s
            for lista in indici["per_nome"].values()
            for s in lista
            if chiave in normalizza_nome_giocatore(s.nome)
        ]
        if len(ovunque) == 1:
            return ovunque[0]
    return None


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
) -> EsitoAggiornamento:
    """Scarica, legge e consolida. Non alza: racconta.

    `apri` e' iniettabile perche' i test non hanno rete e la rete non ha
    voglia di essere prevedibile.
    """
    stagione_ = stagione_ or stagione(oggi)
    esito = EsitoAggiornamento(stagione=stagione_, quando=datetime.now())

    indirizzo_listone = url_quotazioni(stagione_)
    try:
        quotazioni = apri(indirizzo_listone)
    except FonteNonRaggiungibile as errore:
        esito.fonti.append(
            StatoFonte("Listone Fantacalcio.it", indirizzo_listone, False, str(errore))
        )
        return esito

    indirizzo_stipendi = url_capology(stagione_)
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


# --- il file unico ----------------------------------------------------------

COLONNE_CSV = (
    "id_ufficiale",
    "nome",
    "club",
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
                "/".join(riga.ruoli),
                "" if riga.quotazione is None else riga.quotazione,
                "" if riga.fvm is None else riga.fvm,
                f"{riga.ingaggio:.0f}",
                riga.nazionalita,
                riga.data_nascita.isoformat() if riga.data_nascita else "",
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

        fuori.append(
            {
                "id": identificativo,
                "id_ufficiale": riga.id_ufficiale,
                "nome": riga.nome,
                "club": riga.club,
                "ruoli": ";".join(riga.ruoli),
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
    noti = 0
    if esistenti is not None and not esistenti.empty:
        noti = len(esistenti)
    arch.scrivi("giocatori", da_scrivere, chiave="id")
    return {
        "totali": len(da_scrivere),
        "nuovi": max(len(da_scrivere) - noti, 0),
        "con_stipendio": sum(1 for r in righe if r.ingaggio > 0),
    }
