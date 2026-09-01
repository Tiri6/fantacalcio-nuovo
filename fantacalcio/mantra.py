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

**Cosa non sappiamo ancora.** La tabella marca quindici caselle con uno, due o
tre asterischi, e la legenda sta sotto l'immagine che abbiamo. Finche' non
arriva, quelle caselle si trattano come `SPECIALE` e si comportano come un
adattamento con malus: sicuramente non sono divieti — altrimenti sarebbero
`NO` — e cosi' il conto sbaglia al massimo di un punto, mai il verso. Quando
la legenda arriva si cambia `INTERPRETAZIONE_ASTERISCHI`, che e' una riga.
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


# In attesa della legenda: le caselle con asterisco si pagano come un
# adattamento normale. Cambiare questa mappa cambia tutto il comportamento.
INTERPRETAZIONE_ASTERISCHI = {
    Esito.SPECIALE_1: Esito.MALUS,
    Esito.SPECIALE_2: Esito.MALUS,
    Esito.SPECIALE_3: Esito.MALUS,
}


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


def esito_effettivo(ruoli_uscito, ruoli_entrato) -> Esito:
    """Come sopra, con gli asterischi risolti: `LIBERA`, `MALUS` o `VIETATA`."""
    esito = esito_sostituzione(ruoli_uscito, ruoli_entrato)
    return INTERPRETAZIONE_ASTERISCHI.get(esito, esito)


def costo_sostituzione(ruoli_uscito, ruoli_entrato, malus: float) -> float | None:
    """Quanto costa quel cambio: 0, il malus, oppure `None` se non si puo' fare."""
    esito = esito_effettivo(ruoli_uscito, ruoli_entrato)
    if esito is Esito.VIETATA:
        return None
    return malus if esito is Esito.MALUS else 0.0
