"""Quando gli anni di contratto si possono ancora correggere.

Dopo una draft room — quella di inizio stagione o una di riparazione — chi ha
appena assegnato i giocatori ha una finestra per sistemare gli anni: il draft
si fa di corsa, e un contratto scritto male va potuto correggere prima che
conti. La finestra si chiude **con l'inizio della giornata di campionato
successiva**, nello stesso istante in cui si bloccano le formazioni.

Quell'istante e' uno solo di proposito. «Il giorno prima della giornata» e «il
giorno della giornata» sono due frasi che la lega ha usato tutte e due, e sono
diverse di ventiquattr'ore: legandosi al calcio d'inizio non si deve scegliere
fra le due, perche' nessuna delle due permette di cambiare un contratto a
partita cominciata — che e' il punto.

**Questa finestra e' in tensione con l'articolo 8**, che dice che la durata
non si tocca «ne' in sede di scambio ne' con altra operazione». Vedi
`PUNTI_APERTI.md`: finche' la lega non vota, lo switch sta in `OpzioniLega` e
la finestra esiste solo se e' acceso.
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timedelta

from .formazioni import MINUTI_DI_ANTICIPO


@dataclass(frozen=True)
class FinestraAnni:
    """Se si possono ancora correggere gli anni, e fino a quando."""

    aperta: bool
    chiude_il: datetime | None
    motivo: str

    @property
    def manca(self) -> timedelta | None:
        """Quanto resta, se la finestra ha una fine conosciuta."""
        if not self.aperta or self.chiude_il is None:
            return None
        return self.chiude_il - datetime.now()


def finestra_modifica_anni(
    chiusura_draft: datetime | None,
    inizio_prossima_giornata: datetime | None,
    adesso: datetime | None = None,
    anticipo_minuti: int = MINUTI_DI_ANTICIPO,
) -> FinestraAnni:
    """La finestra fra la fine di una draft room e la giornata successiva.

    Tre casi che non si confondono:

    - **Nessuna draft room conclusa**: non c'e' niente da correggere, e la
      finestra non si apre. Aprirla sempre vorrebbe dire che gli anni si
      cambiano tutto l'anno, cioe' la cosa che l'articolo 8 vieta.
    - **Draft conclusa e nessuna giornata in programma**: resta aperta. Una
      giornata senza data non e' una giornata programmata, e chiudere una
      finestra su una scadenza che nessuno ha fissato sarebbe peggio che
      lasciarla aperta — e' la stessa scelta di `stato_blocco`.
    - **Draft conclusa e giornata in programma**: si chiude `anticipo_minuti`
      prima del calcio d'inizio, lo stesso istante delle formazioni.
    """
    adesso = adesso or datetime.now()

    if chiusura_draft is None:
        return FinestraAnni(
            False,
            None,
            "Gli anni si correggono solo dopo una draft room: non ce n'e' una "
            "conclusa.",
        )
    if adesso < chiusura_draft:
        return FinestraAnni(
            False,
            None,
            "La draft room non e' ancora chiusa: gli anni si assegnano li'.",
        )

    if inizio_prossima_giornata is None:
        return FinestraAnni(
            True,
            None,
            "Nessuna giornata in programma: la finestra resta aperta finche' "
            "non ce n'e' una.",
        )

    limite = inizio_prossima_giornata - timedelta(minutes=anticipo_minuti)
    if adesso >= limite:
        return FinestraAnni(
            False,
            limite,
            f"La giornata e' cominciata alle "
            f"{inizio_prossima_giornata.strftime('%H:%M di %d/%m')}: da li' gli "
            f"anni non si toccano piu'.",
        )
    return FinestraAnni(True, limite, "")
