"""Le statistiche di stagione di un giocatore, ricavate dalla nostra storia.

Niente fonti esterne: solo i voti che il presidente ha importato (`voti`) e le
formazioni salvate. Il calcolo sta qui e non nel browser: la pagina riceve
numeri gia' fatti e li stampa, cosi' il giorno che la lega cambia cosa conta
nella media non c'e' una seconda copia da correggere.

**Due medie.** `media` e' la media voto (MV, il voto puro del giornale);
`fantamedia` e' la FM, cioe' voto piu' bonus e malus della lega. Si mostrano
tutte e due, e i bonus li passa chi chiama: sono quelli della lega.
"""

from __future__ import annotations

from collections.abc import Iterable, Mapping
from dataclasses import dataclass

from .formazioni import Voto, punteggio_giocatore
from .leghe import Bonus


@dataclass(frozen=True)
class StatisticheGiocatore:
    giocatore_id: int
    #: giornate in cui ha preso voto
    presenze: int
    #: di queste, quelle in cui era titolare in una formazione
    da_titolare: int
    #: MV, media del voto puro. None se non ha mai preso voto: la pagina
    #: mostra un trattino, non uno zero
    media: float | None
    #: FM, media del voto con bonus e malus. None come sopra
    fantamedia: float | None
    #: percentuale intera 0-100, None come sopra
    percentuale_titolare: int | None


def statistiche_stagione(
    voti: Iterable[Voto],
    titolari_per_giornata: Mapping[int, set[int]],
    bonus: Bonus | None = None,
) -> dict[int, StatisticheGiocatore]:
    """MV, FM e percentuale di titolarita' per ogni giocatore con almeno un voto.

    Contano solo le giornate in cui il giocatore ha preso voto (`ha_giocato`):
    un senza voto non abbassa la media ne' la percentuale. La percentuale e'
    la quota di quelle giornate in cui stava fra i titolari.
    """
    bonus = bonus or Bonus()
    somme: dict[int, float] = {}
    fanta: dict[int, float] = {}
    presenze: dict[int, int] = {}
    titolare: dict[int, int] = {}
    visti: set[tuple[int, int]] = set()
    for v in voti:
        if not v.ha_giocato or (v.giocatore_id, v.giornata) in visti:
            continue
        visti.add((v.giocatore_id, v.giornata))
        g = v.giocatore_id
        somme[g] = somme.get(g, 0.0) + float(v.voto)
        fanta[g] = fanta.get(g, 0.0) + punteggio_giocatore(v, bonus)
        presenze[g] = presenze.get(g, 0) + 1
        if g in titolari_per_giornata.get(v.giornata, ()):
            titolare[g] = titolare.get(g, 0) + 1
    return {
        g: StatisticheGiocatore(
            giocatore_id=g,
            presenze=n,
            da_titolare=titolare.get(g, 0),
            media=round(somme[g] / n, 2),
            fantamedia=round(fanta[g] / n, 2),
            percentuale_titolare=round(100 * titolare.get(g, 0) / n),
        )
        for g, n in presenze.items()
    }
