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

    # I pesi dell'articolo 3 sono cinque, cioe' una lega da dieci. Con una
    # fascia piu' numerosa il regolamento non dice quanto pesano le squadre in
    # piu', e inventarlo sarebbe decidere al posto della lega. Meglio dirlo:
    # senza questo controllo `random.choices` alzava «The number of weights
    # does not match the population», che non spiega niente a nessuno.
    meta = len(squadre) // 2
    if meta > len(PESI_FASCIA):
        raise ValueError(
            f"I pesi dell'articolo 3 sono {len(PESI_FASCIA)}, cioe' una lega "
            f"da {len(PESI_FASCIA) * 2} squadre: con {len(squadre)} ogni "
            f"fascia ne avrebbe {meta} e il regolamento non dice quanto "
            f"pesano quelle in piu'."
        )

    rng = rng or random.Random()

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


# ---------------------------------------------------------------------------
# Il tabellone delle chiamate
# ---------------------------------------------------------------------------
#
# Sopra c'e' la Lottery dell'articolo 3, che decide *chi chiama per primo*.
# Qui sotto c'e' la cosa piu' semplice e piu' usata: dato un ordine, di chi e'
# il turno alla chiamata numero N. Serpente o ordine fisso: la differenza sta
# tutta nel fatto che i round pari si leggano al contrario.


@dataclass(frozen=True)
class Chiamata:
    """Una singola chiamata del draft."""

    numero: int  # progressivo assoluto, dalla prima chiamata del draft
    round: int
    posizione: int  # posizione dentro il round, da 1
    squadra: str

    @property
    def etichetta(self) -> str:
        return f"Round {self.round} · pick {self.posizione}"


def chiamata_numero(
    ordine: Sequence[str], numero: int, serpente: bool = True
) -> Chiamata:
    """Chi chiama alla chiamata `numero` (dalla 1), senza costruire il tabellone.

    Con `serpente` i round pari vanno al contrario: l'ultima squadra del round
    dispari chiama due volte di fila, che e' esattamente il compenso per aver
    aspettato tutti gli altri.
    """
    squadre = list(ordine)
    if not squadre:
        raise ValueError("Serve l'ordine di chiamata di almeno una squadra")
    if numero < 1:
        raise ValueError(f"Le chiamate partono da 1, ricevuto {numero}")

    quante = len(squadre)
    round_ = (numero - 1) // quante + 1
    posizione = (numero - 1) % quante + 1
    indice = quante - posizione if (serpente and round_ % 2 == 0) else posizione - 1
    return Chiamata(
        numero=numero, round=round_, posizione=posizione, squadra=squadre[indice]
    )


def turni_di_chiamata(
    ordine: Sequence[str], round_totali: int, serpente: bool = True
) -> list[Chiamata]:
    """Tutte le chiamate di `round_totali` round, in fila."""
    if round_totali < 1:
        raise ValueError(f"Servono almeno un round, ricevuti {round_totali}")
    return [
        chiamata_numero(ordine, numero, serpente)
        for numero in range(1, len(ordine) * round_totali + 1)
    ]


def griglia_chiamate(
    ordine: Sequence[str], round_totali: int, serpente: bool = True
) -> list[tuple[int, tuple[str, ...]]]:
    """Il tabellone round per round, pronto da mostrare."""
    chiamate = turni_di_chiamata(ordine, round_totali, serpente)
    per_round: dict[int, list[str]] = {}
    for chiamata in chiamate:
        per_round.setdefault(chiamata.round, []).append(chiamata.squadra)
    return [(numero, tuple(squadre)) for numero, squadre in sorted(per_round.items())]
