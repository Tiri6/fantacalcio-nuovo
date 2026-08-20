"""Articolo 3: draft, Draft Lottery e ordine di chiamata.

Il draft di Settembre non e' un'asta a rilancio: le pick sono assegnate dalla
Lottery, e l'ordine di chiamata cambia di round in round.
"""

from __future__ import annotations

import random
from collections import Counter
from collections.abc import Sequence
from dataclasses import dataclass

# Articolo 3: 50% alla peggio classificata della fascia, poi a scalare.
PESI_FASCIA = (50, 20, 15, 10, 5)

# I round multipli di questo valore seguono l'ordine di classifica invece
# dell'ordine determinato dalla Lottery.
PERIODO_ROUND_CLASSIFICA = 3


@dataclass(frozen=True)
class EsitoLottery:
    """Ordine delle pick uscito dalla Lottery, piu' le due fasce di partenza."""

    ordine: tuple[str, ...]
    fascia_bassa: tuple[str, ...]
    fascia_alta: tuple[str, ...]

    def pick_di(self, squadra: str) -> int:
        return self.ordine.index(squadra) + 1


def _estrai_fascia(fascia: Sequence[str], rng: random.Random) -> list[str]:
    """Estrae senza reimmissione con i pesi dell'articolo 3.

    `fascia` va passata dalla peggio classificata alla meglio classificata:
    e' a lei che spetta il 50%. Dopo ogni estrazione i pesi rimasti vengono
    rinormalizzati sulle squadre ancora in gioco.
    """
    rimaste = list(fascia)
    pesi = list(PESI_FASCIA[: len(fascia)])
    estratte: list[str] = []

    while rimaste:
        scelta = rng.choices(rimaste, weights=pesi, k=1)[0]
        indice = rimaste.index(scelta)
        rimaste.pop(indice)
        pesi.pop(indice)
        estratte.append(scelta)

    return estratte


def sorteggia_lottery(
    classifica_precedente: Sequence[str], rng: random.Random | None = None
) -> EsitoLottery:
    """Articolo 3: due estrazioni distinte per le pick 1-5 e 6-10.

    `classifica_precedente` va dalla 1a all'ultima classificata. Le pick 1-5
    si sorteggiano tra la seconda meta' della classifica (dal 10o al 6o posto),
    le pick 6-10 tra la prima meta' (dal 5o al 1o).
    """
    squadre = list(classifica_precedente)
    if len(squadre) % 2:
        raise ValueError(
            f"La Lottery divide la classifica in due fasce uguali: "
            f"{len(squadre)} squadre non sono divisibili in due."
        )
    if len(set(squadre)) != len(squadre):
        raise ValueError("La classifica contiene squadre duplicate")

    rng = rng or random.Random()
    meta = len(squadre) // 2

    # Dalla peggio classificata verso l'alto: e' l'ordine dei pesi.
    fascia_bassa = list(reversed(squadre[meta:]))  # 10a -> 6a
    fascia_alta = list(reversed(squadre[:meta]))  # 5a -> 1a

    ordine = _estrai_fascia(fascia_bassa, rng) + _estrai_fascia(fascia_alta, rng)
    return EsitoLottery(
        ordine=tuple(ordine),
        fascia_bassa=tuple(fascia_bassa),
        fascia_alta=tuple(fascia_alta),
    )


def ordine_round(
    numero_round: int,
    ordine_lottery: Sequence[str],
    classifica_precedente: Sequence[str],
) -> tuple[str, ...]:
    """Chi chiama, e in che ordine, in un dato round del draft di Settembre.

    - round 1: ordine della Lottery;
    - round 2: ordine invertito (i due turni a serpente);
    - round multipli di 3: ordine di arrivo della stagione precedente, dalla 1a;
    - tutti gli altri: ordine della Lottery.
    """
    if numero_round < 1:
        raise ValueError(f"Il round deve partire da 1, ricevuto {numero_round}")

    if numero_round % PERIODO_ROUND_CLASSIFICA == 0:
        return tuple(classifica_precedente)
    if numero_round == 2:
        return tuple(reversed(ordine_lottery))
    return tuple(ordine_lottery)


def tabellone_draft(
    round_totali: int,
    ordine_lottery: Sequence[str],
    classifica_precedente: Sequence[str],
) -> list[tuple[int, tuple[str, ...]]]:
    """Ordine di chiamata di tutti i round, pronto da mostrare a schermo."""
    return [
        (n, ordine_round(n, ordine_lottery, classifica_precedente))
        for n in range(1, round_totali + 1)
    ]


def ordine_riparazione(classifica_attuale: Sequence[str]) -> tuple[str, ...]:
    """Articolo 3: nell'asta di riparazione tutti i turni seguono l'ordine
    inverso di classifica al momento dell'apertura della finestra."""
    return tuple(reversed(classifica_attuale))


def distribuzione_pick(
    classifica_precedente: Sequence[str],
    simulazioni: int = 20_000,
    seme: int | None = 0,
) -> dict[str, dict[int, float]]:
    """Probabilita' stimata di ogni pick per ogni squadra.

    I pesi dell'articolo 3 valgono per la prima estrazione; le probabilita'
    delle pick successive dipendono da chi e' gia' uscito, quindi si stimano
    per simulazione invece di calcolarle in chiuso.
    """
    rng = random.Random(seme)
    conteggi: dict[str, Counter] = {s: Counter() for s in classifica_precedente}

    for _ in range(simulazioni):
        esito = sorteggia_lottery(classifica_precedente, rng)
        for posizione, squadra in enumerate(esito.ordine, start=1):
            conteggi[squadra][posizione] += 1

    return {
        squadra: {pick: conteggio / simulazioni for pick, conteggio in sorted(c.items())}
        for squadra, c in conteggi.items()
    }
