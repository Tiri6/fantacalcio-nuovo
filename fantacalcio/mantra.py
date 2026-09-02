"""La tabella delle sostituzioni del Mantra, per ruolo e non per reparto.

E' la tabella ufficiale della piattaforma: dice, per ogni coppia
«chi esce → chi entra», se il cambio si puo' fare e se costa il malus. Le
**righe sono il ruolo di chi esce**, le **colonne il ruolo di chi entra**.

La direzione non e' un dettaglio, perche' la tabella e' asimmetrica: per
coprire una punta si puo' usare un difensore (con malus), ma per coprire un
difensore non si puo' usare una punta. E' il principio che il regolamento
scrive a parole — *l'adattabilita' si concretizza solo con calciatori della
stessa linea di gioco o di linee piu' arretrate* — e la tabella lo declina
caso per caso, con qualche eccezione fatta a mano.

Il portiere e' fuori da tutto: riga e colonna `Por` sono chiuse, tranne la
casella con se' stesso.

**Gli asterischi.** Quindici caselle ne portano uno, due o tre, e la legenda
li scioglie guardando **la casella del modulo** che si sta riempiendo:

- `*`   — OK se la casella ammette quel ruolo in alternativa, altrimenti NO;
- `**`  — OK se la casella lo ammette, altrimenti malus;
- `***` — OK se la casella lo ammette, **NO nel 4-1-4-1**, altrimenti malus.

E' anche il motivo per cui le righe si leggono come **la casella da coprire**
e non come il giocatore che esce: senza sapere che posto e', l'asterisco non
si potrebbe sciogliere. La regola generale che ne esce e' semplice — se il
ruolo del giocatore e' fra quelli che la casella ammette, gioca gratis — e
tutto il resto e' la tabella.
"""

from __future__ import annotations

from enum import Enum

# I dodici ruoli della tabella, dall'attacco alla porta. Sulla piattaforma il
# portiere si scrive «P»; nel listone e in tutto il resto del progetto e'
# «Por», e qui vale quello, cosi' i ruoli dei giocatori si confrontano senza
# traduzioni sparse per il codice.
RUOLI_TABELLA = (
    "Pc",
    "A",
    "T",
    "W",
    "C",
    "M",
    "E",
    "B",
    "Dc",
    "Dd",
    "Ds",
    "Por",
)


class Esito(Enum):
    """Cosa succede se quel giocatore entra al posto di quell'altro."""

    LIBERA = "OK"
    MALUS = "-1"
    SPECIALE_1 = "*"
    SPECIALE_2 = "**"
    SPECIALE_3 = "***"
    VIETATA = "NO"

    @property
    def possibile(self) -> bool:
        return self is not Esito.VIETATA


# Gli asterischi quando la casella *non* ammette quel ruolo in alternativa:
# se lo ammette sono sempre OK, e lo decide `esito_in_casella`.
ASTERISCHI_NON_IN_ALTERNATIVA = {
    Esito.SPECIALE_1: Esito.VIETATA,
    Esito.SPECIALE_2: Esito.MALUS,
    Esito.SPECIALE_3: Esito.MALUS,
}

# L'unica eccezione nominata dalla legenda: nel 4-1-4-1 il triplo asterisco
# (lo scambio fra T e W) e' un divieto, perche' li' le due caselle sono
# distinte e nessuna delle due ammette l'altro ruolo.
MODULO_SENZA_TRIPLO_ASTERISCO = "4-1-4-1"


# La tabella, trascritta riga per riga. Prima colonna = chi esce.
_RIGHE = """
Pc   OK  OK  -1  -1  -1  -1  -1  -1  -1  -1  -1  NO
A    *   OK  **  **  -1  -1  -1  -1  -1  -1  -1  NO
T    *   *   OK  *** **  -1  -1  -1  -1  -1  -1  NO
W    NO  *   *** OK  -1  -1  **  -1  -1  -1  -1  NO
C    NO  NO  *   NO  OK  **  -1  -1  -1  -1  -1  NO
M    NO  NO  NO  NO  *   OK  -1  -1  -1  -1  -1  NO
E    NO  NO  NO  *   NO  -1  OK  -1  -1  -1  -1  NO
B    NO  NO  NO  NO  NO  NO  NO  OK  OK  -1  -1  NO
Dc   NO  NO  NO  NO  NO  NO  NO  **  OK  -1  -1  NO
Dd   NO  NO  NO  NO  NO  NO  NO  -1  -1  OK  -1  NO
Ds   NO  NO  NO  NO  NO  NO  NO  -1  -1  -1  OK  NO
Por  NO  NO  NO  NO  NO  NO  NO  NO  NO  NO  NO  OK
"""


def _leggi_tabella() -> dict[str, dict[str, Esito]]:
    """Dal testo qui sopra alla tabella vera, con i controlli del caso.

    Si legge da una stringa e non da un dizionario scritto a mano perche' una
    griglia di 144 caselle, in colonne allineate, si confronta con l'originale
    guardandola. Un dizionario di dizionari no.
    """
    per_simbolo = {e.value: e for e in Esito}
    tabella: dict[str, dict[str, Esito]] = {}
    for linea in _RIGHE.strip().splitlines():
        pezzi = linea.split()
        uscito, celle = pezzi[0], pezzi[1:]
        if len(celle) != len(RUOLI_TABELLA):
            raise ValueError(
                f"La riga {uscito} ha {len(celle)} caselle invece di {len(RUOLI_TABELLA)}"
            )
        tabella[uscito] = {
            entrato: per_simbolo[cella]
            for entrato, cella in zip(RUOLI_TABELLA, celle, strict=True)
        }
    mancanti = set(RUOLI_TABELLA) - set(tabella)
    if mancanti:
        raise ValueError(f"Mancano le righe: {', '.join(sorted(mancanti))}")
    return tabella


TABELLA_SOSTITUZIONI = _leggi_tabella()


def esito_grezzo(ruolo_uscito: str, ruolo_entrato: str) -> Esito:
    """La casella della tabella, cosi' com'e' scritta.

    Un ruolo che la tabella non conosce (una colonna vuota nel listone, una
    grafia diversa) non blocca niente: si risponde `VIETATA`, e chi chiama
    decide. Meglio un cambio in meno che un punteggio inventato.
    """
    return TABELLA_SOSTITUZIONI.get(ruolo_uscito, {}).get(ruolo_entrato, Esito.VIETATA)


def esito_sostituzione(ruoli_uscito, ruoli_entrato) -> Esito:
    """Il miglior esito possibile fra due giocatori, che di ruoli ne hanno piu' d'uno.

    «Dd/E» che entra per un «W/T» ha quattro caselle da guardare: vale la piu'
    favorevole, perche' il giocatore in campo ci va una volta sola e lo si
    schiera nel modo che gli riesce meglio.
    """
    ordine = [
        Esito.LIBERA,
        Esito.SPECIALE_1,
        Esito.SPECIALE_2,
        Esito.SPECIALE_3,
        Esito.MALUS,
        Esito.VIETATA,
    ]
    esiti = [
        esito_grezzo(uscito, entrato)
        for uscito in (ruoli_uscito or ())
        for entrato in (ruoli_entrato or ())
    ]
    if not esiti:
        return Esito.VIETATA
    return min(esiti, key=ordine.index)


# --- le caselle dei moduli --------------------------------------------------
#
# Ogni modulo prescrive undici caselle, e ognuna dice quali ruoli ci stanno di
# diritto. E' la seconda meta' del Mantra: la tabella qui sopra dice chi puo'
# coprire cosa, questa dice cosa c'e' da coprire.
#
# Le barre verticali separano le **righe del campo**, cosi' come si vedono
# nello schema ufficiale, e servono anche a disegnarle. Il numero di caselle
# di ogni riga deve corrispondere ai numeri del nome: e' il controllo che
# rende sicura una trascrizione fatta a mano da un'immagine.
#
# ATTENZIONE: qui ci sono solo i moduli letti con certezza dallo schema
# ufficiale 2026/27. Gli altri non si indovinano: finche' non ci sono, il
# sito li tratta per reparto come faceva prima (vedi PUNTI_APERTI.md).
_CASELLE = """
3-4-3    | Por | Dc Dc Dc/B  | E M/C C E    | W/A W/A A/Pc
3-4-1-2  | Por | Dc Dc Dc/B  | E M/C C E    | T          | A/Pc A/Pc
4-3-1-2  | Por | Dd Dc Dc Ds | M/C M C      | T          | T/A A/Pc
4-1-4-1  | Por | Dd Dc Dc Ds | M            | E/W C/T T W | A/Pc
4-2-3-1  | Por | Dd Dc Dc Ds | M/C M/C      | W/T T W/A  | A/Pc
"""


def _leggi_caselle() -> dict[str, tuple[tuple[str, ...], ...]]:
    """Dal testo qui sopra ai moduli, controllando che i conti tornino."""
    import re

    moduli: dict[str, tuple[tuple[str, ...], ...]] = {}
    for linea in _CASELLE.strip().splitlines():
        nome, *gruppi = (pezzo.strip() for pezzo in linea.split("|"))
        righe = tuple(tuple(g.split("/")) for gruppo in gruppi for g in gruppo.split())
        per_riga = [len(gruppo.split()) for gruppo in gruppi]
        attesi = [1] + [int(n) for n in re.findall(r"\d+", nome)]
        if per_riga != attesi:
            raise ValueError(
                f"Il modulo {nome} ha righe da {per_riga} caselle, "
                f"ma il nome ne chiede {attesi}"
            )
        sconosciuti = {r for casella in righe for r in casella} - set(RUOLI_TABELLA)
        if sconosciuti:
            raise ValueError(
                f"Il modulo {nome} usa ruoli che la tabella non conosce: "
                f"{', '.join(sorted(sconosciuti))}"
            )
        moduli[nome] = righe
    return moduli


def _leggi_righe_moduli() -> dict[str, tuple[tuple[tuple[str, ...], ...], ...]]:
    """Le stesse caselle, ma raggruppate per riga di campo: servono a disegnare."""
    moduli: dict[str, tuple[tuple[tuple[str, ...], ...], ...]] = {}
    for linea in _CASELLE.strip().splitlines():
        nome, *gruppi = (pezzo.strip() for pezzo in linea.split("|"))
        moduli[nome] = tuple(
            tuple(tuple(g.split("/")) for g in gruppo.split()) for gruppo in gruppi
        )
    return moduli


CASELLE_PER_MODULO = _leggi_caselle()
RIGHE_PER_MODULO = _leggi_righe_moduli()


def caselle_di(modulo: str) -> tuple[tuple[str, ...], ...]:
    """Le undici caselle di un modulo, in ordine. Vuoto se non lo conosciamo."""
    return CASELLE_PER_MODULO.get(str(modulo), ())


def _sciogli(esito: Esito, modulo: str) -> Esito:
    """Un asterisco diventa OK, malus o divieto — qui si sa gia' che la
    casella *non* ammette quel ruolo in alternativa."""
    if esito is Esito.SPECIALE_3 and str(modulo) == MODULO_SENZA_TRIPLO_ASTERISCO:
        return Esito.VIETATA
    return ASTERISCHI_NON_IN_ALTERNATIVA.get(esito, esito)


def esito_in_casella(ruoli_casella, ruoli_giocatore, modulo: str = "") -> Esito:
    """Se quel giocatore puo' occupare quella casella, e a che prezzo.

    Prima la regola semplice: se un suo ruolo e' fra quelli che la casella
    ammette, gioca gratis. E' la stessa frase che scioglie gli asterischi —
    *«OK negli schemi con i ruoli in alternativa»* — quindi vale sia per la
    casella «A/Pc» riempita da una punta sia per il triplo asterisco fra T e W
    quando il modulo prevede una casella «W/T».

    Altrimenti si guarda la tabella, casella per ruolo, e si prende l'esito
    migliore: un giocatore in campo ci va una volta sola, e lo si schiera nel
    modo che gli riesce meglio.
    """
    ruoli_casella = tuple(ruoli_casella or ())
    ruoli_giocatore = tuple(ruoli_giocatore or ())
    if any(r in ruoli_casella for r in ruoli_giocatore):
        return Esito.LIBERA

    ordine = (Esito.LIBERA, Esito.MALUS, Esito.VIETATA)
    esiti = [
        _sciogli(esito_grezzo(casella, giocatore), modulo)
        for casella in ruoli_casella
        for giocatore in ruoli_giocatore
    ]
    return min(esiti, key=ordine.index) if esiti else Esito.VIETATA


def costo_in_casella(
    ruoli_casella, ruoli_giocatore, malus: float, modulo: str = ""
) -> float | None:
    """Quanto costa schierarlo li': 0, il malus, o `None` se non si puo'."""
    esito = esito_in_casella(ruoli_casella, ruoli_giocatore, modulo)
    if esito is Esito.VIETATA:
        return None
    return malus if esito is Esito.MALUS else 0.0
