"""Dati anagrafici di chi si iscrive: data, sesso, citta', squadra del cuore.

Sono informazioni della persona, non della lega: stanno qui e non in
`autenticazione.py`, che si occupa di password e permessi.

Le date si scrivono all'italiana (gg/mm/aaaa) perche' e' cosi' che le scrive
chi compila, e un modulo che pretende il formato ISO e' un modulo che fa
sbagliare.
"""

from __future__ import annotations

import re
from datetime import date
from enum import Enum

ETA_MINIMA = 13
ETA_MASSIMA = 120


class DataNonValida(ValueError):
    pass


class Sesso(Enum):
    MASCHIO = "Maschio"
    FEMMINA = "Femmina"
    ALTRO = "Altro"
    NON_DICHIARATO = "Preferisco non dirlo"

    @property
    def etichetta(self) -> str:
        return self.value


SEPARATORI = re.compile(r"[/\-. ]")


def leggi_data_italiana(testo: str, oggi: date | None = None) -> date:
    """Da 'gg/mm/aaaa' a una data. Accetta anche '-', '.' e lo spazio.

    Rifiuta le date impossibili e quelle assurde per un iscritto: nel futuro,
    o di chi avrebbe piu' di 120 anni. Un anno digitato male (1066 invece di
    1966) e' l'errore piu' comune, e senza questo controllo entrerebbe.
    """
    if not isinstance(testo, str) or not testo.strip():
        raise DataNonValida("La data di nascita non puo' essere vuota")

    pezzi = [p for p in SEPARATORI.split(testo.strip()) if p]
    if len(pezzi) != 3:
        raise DataNonValida(
            f"'{testo}' non e' una data: si scrive gg/mm/aaaa, per esempio 24/03/1991"
        )

    try:
        giorno, mese, anno = (int(p) for p in pezzi)
    except ValueError:
        raise DataNonValida(f"'{testo}' contiene caratteri che non sono numeri") from None

    if anno < 100:  # '91' vuol dire 1991, non l'anno 91
        anno += 1900 if anno > 30 else 2000

    try:
        nascita = date(anno, mese, giorno)
    except ValueError as errore:
        raise DataNonValida(f"'{testo}' non e' una data esistente ({errore})") from None

    oggi = oggi or date.today()
    if nascita > oggi:
        raise DataNonValida("La data di nascita non puo' essere nel futuro")
    if anni_compiuti(nascita, oggi) > ETA_MASSIMA:
        raise DataNonValida(
            f"Hai scritto {anno}: controlla l'anno, sono piu' di {ETA_MASSIMA} anni fa"
        )
    if anni_compiuti(nascita, oggi) < ETA_MINIMA:
        raise DataNonValida(f"Bisogna avere almeno {ETA_MINIMA} anni per iscriversi")
    return nascita


def anni_compiuti(nascita: date, oggi: date | None = None) -> int:
    oggi = oggi or date.today()
    return (
        oggi.year - nascita.year - ((oggi.month, oggi.day) < (nascita.month, nascita.day))
    )


def scrivi_data_italiana(giorno: date | None) -> str:
    return giorno.strftime("%d/%m/%Y") if giorno else ""


# --- Squadra del cuore ------------------------------------------------------

ALTRO_ITALIA = "Altro (Italia)"
ALTRO_ESTERO = "Altro (Estero)"
NESSUNA = "Nessuna / non tifo"

# Elenchi di partenza. La Serie A vera si ricava dal listone caricato (vedi
# `squadre_preferite`), quindi questa lista serve solo quando il listone non
# c'e' ancora. La B non compare nel listone e va aggiornata a inizio stagione.
SERIE_A_PREDEFINITA = (
    "Atalanta",
    "Bologna",
    "Cagliari",
    "Como",
    "Cremonese",
    "Fiorentina",
    "Genoa",
    "Inter",
    "Juventus",
    "Lazio",
    "Lecce",
    "Milan",
    "Napoli",
    "Parma",
    "Pisa",
    "Roma",
    "Sassuolo",
    "Torino",
    "Udinese",
    "Verona",
)

SERIE_B_PREDEFINITA = (
    "Avellino",
    "Bari",
    "Carrarese",
    "Catanzaro",
    "Cesena",
    "Empoli",
    "Frosinone",
    "Juve Stabia",
    "Mantova",
    "Modena",
    "Monza",
    "Padova",
    "Palermo",
    "Pescara",
    "Reggiana",
    "Salernitana",
    "Sampdoria",
    "Spezia",
    "SudTirol",
    "Venezia",
)


def squadre_preferite(club_di_serie_a: list[str] | None = None) -> list[str]:
    """Le voci della tendina, in ordine: Serie A, Serie B, le due «Altro».

    `club_di_serie_a` arriva dal listone ufficiale quando c'e': cosi' l'elenco
    e' quello vero della stagione in corso invece di una lista da aggiornare a
    mano ogni anno.
    """
    serie_a = (
        sorted(set(club_di_serie_a)) if club_di_serie_a else list(SERIE_A_PREDEFINITA)
    )
    serie_b = [s for s in SERIE_B_PREDEFINITA if s not in set(serie_a)]
    return [*serie_a, *serie_b, ALTRO_ITALIA, ALTRO_ESTERO, NESSUNA]


def squadra_valida(scelta: str, disponibili: list[str] | None = None) -> str:
    """Normalizza la scelta. Una squadra sconosciuta diventa «Altro (Italia)»."""
    pulita = (scelta or "").strip()
    if not pulita:
        return NESSUNA
    ammesse = disponibili if disponibili is not None else squadre_preferite()
    if pulita in ammesse:
        return pulita
    return ALTRO_ITALIA
