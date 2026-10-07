"""La lega di chi sta chiamando, e i parametri che ne discendono.

Streamlit teneva lega, parametri e data U21 in `ui.py`, dietro la cache. Qui
si ricavano a ogni richiesta dallo stesso dominio: sono poche righe e
leggerle fresche costa meno che spiegare a dieci persone perche' la pagina
mostra le regole di ieri.
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import date

from fantacalcio.autenticazione import Utente
from fantacalcio.competizioni import data_riferimento_u21
from fantacalcio.data import Archivio, archivio, carica_leghe
from fantacalcio.leghe import Lega
from fantacalcio.regole import CalendarioStagione, ParametriLega

# La stessa data che usa Streamlit. Non e' il riferimento U21 (quello e' il 31
# agosto): e' la data del draft di settembre, da cui dipendono le scadenze.
DATA_DRAFT = date(2026, 9, 15)


@dataclass(frozen=True)
class Contesto:
    arch: Archivio
    lega: Lega | None
    parametri: ParametriLega
    # Il 31 agosto della stagione: data fissa voluta dalla lega, non quella
    # del draft, cosi' lo status Under 21 non si muove se l'asta slitta.
    riferimento_u21: date
    # Quante giornate si giocano e quando aprono le finestre di mercato.
    # Streamlit ne tiene una copia fissa in `ui.CALENDARIO`; qui si costruisce
    # dalle opzioni della lega, che il presidente puo' cambiare per votazione.
    calendario: CalendarioStagione

    @property
    def stagione(self) -> str:
        return self.lega.stagione if self.lega else self.parametri.stagione


def contesto_di(utente: Utente) -> Contesto:
    arch = archivio()
    lega = carica_leghe(arch).get(utente.lega_id) if utente.lega_id else None
    parametri = ParametriLega()
    stagione = lega.stagione if lega else parametri.stagione
    return Contesto(
        arch=arch,
        lega=lega,
        parametri=parametri,
        riferimento_u21=data_riferimento_u21(stagione),
        calendario=CalendarioStagione(
            data_draft_settembre=DATA_DRAFT,
            giornate_totali=(
                lega.opzioni.giornate_totali
                if lega
                else CalendarioStagione.giornate_totali
            ),
        ),
    )
