"""Chi e' Under 21 italiano lo decide la lega, giocatore per giocatore.

Lo status si valuta al 31 agosto e vale per tutta la stagione
(`competizioni.data_riferimento_u21`); il sito non lo ricalcola da una data di
nascita. Si carica con il CSV delle rose, e qui si corregge a mano.

Il permesso sta nel dominio e non solo nella pagina: un pulsante nascosto non
e' un controllo.
"""

from __future__ import annotations

from .data import Archivio, carica_giocatori, imposta_italiano_u21
from .leghe import Lega, puo_amministrare
from .modelli import Giocatore
from .regole import ParametriLega


class StatusNonModificabile(Exception):
    """Chi chiede non amministra la lega."""


class GiocatoreSconosciuto(LookupError):
    pass


def cambia_status_u21(
    arch: Archivio,
    chi,
    lega: Lega | None,
    giocatore_id: int,
    italiano_u21: bool,
    parametri: ParametriLega | None = None,
) -> Giocatore:
    """Segna o toglie lo status Under 21 italiano. Solo chi amministra la lega.

    Un Under 21 *italiano* e' per forza italiano: chi ha un'altra nazionalita'
    non puo' averlo, ed e' lo stesso controllo che fa l'import delle rose.
    """
    parametri = parametri or ParametriLega()
    if not puo_amministrare(chi, lega):
        raise StatusNonModificabile(
            "Lo status Under 21 lo cambia chi amministra la lega."
        )
    giocatore = carica_giocatori(arch).get(giocatore_id)
    if giocatore is None:
        raise GiocatoreSconosciuto(f"Il giocatore {giocatore_id} non esiste")
    if italiano_u21 and giocatore.nazionalita != parametri.nazionalita_u21:
        raise ValueError(
            f"Un Under 21 italiano deve avere nazionalita' "
            f"«{parametri.nazionalita_u21}»: {giocatore.nome} e' "
            f"«{giocatore.nazionalita}»"
        )
    imposta_italiano_u21(arch, giocatore_id, italiano_u21)
    return carica_giocatori(arch)[giocatore_id]
