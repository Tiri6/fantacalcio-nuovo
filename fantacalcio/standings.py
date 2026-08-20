"""Calendario del campionato e classifica."""

from __future__ import annotations

from collections.abc import Sequence
from dataclasses import dataclass, field

PUNTI_VITTORIA = 3
PUNTI_PAREGGIO = 1
PUNTI_SCONFITTA = 0


@dataclass(frozen=True)
class Partita:
    """Una partita di una giornata. `gol_*` a None = non ancora giocata."""

    giornata: int
    casa: str
    trasferta: str
    gol_casa: int | None = None
    gol_trasferta: int | None = None
    punti_casa: float | None = None
    punti_trasferta: float | None = None

    @property
    def giocata(self) -> bool:
        return self.gol_casa is not None and self.gol_trasferta is not None


@dataclass
class RigaClassifica:
    squadra: str
    giocate: int = 0
    vinte: int = 0
    pareggiate: int = 0
    perse: int = 0
    gol_fatti: int = 0
    gol_subiti: int = 0
    punti: int = 0
    punti_fantacalcio: float = 0.0

    @property
    def differenza_reti(self) -> int:
        return self.gol_fatti - self.gol_subiti


@dataclass(frozen=True)
class Calendario:
    squadre: tuple[str, ...]
    partite: tuple[Partita, ...] = field(default_factory=tuple)

    @property
    def giornate(self) -> int:
        return max((p.giornata for p in self.partite), default=0)

    def giornata(self, numero: int) -> tuple[Partita, ...]:
        return tuple(p for p in self.partite if p.giornata == numero)


_RIPOSA = "__riposa__"


def genera_calendario(squadre: Sequence[str], andata_ritorno: bool = True) -> Calendario:
    """Round robin con l'algoritmo del cerchio (Berger).

    Con un numero dispari di squadre viene aggiunto un turno di riposo, quindi
    ogni giornata ha una squadra che non gioca.
    """
    if len(squadre) < 2:
        raise ValueError("Servono almeno 2 squadre per generare un calendario")
    if len(set(squadre)) != len(squadre):
        raise ValueError("I nomi delle squadre devono essere unici")

    elenco = list(squadre)
    if len(elenco) % 2:
        elenco.append(_RIPOSA)

    meta = len(elenco) // 2
    fisso, ruota = elenco[0], elenco[1:]
    partite: list[Partita] = []

    for turno in range(len(elenco) - 1):
        disposizione = [fisso] + ruota
        casa_lista = disposizione[:meta]
        ospiti_lista = disposizione[meta:][::-1]

        accoppiate = zip(casa_lista, ospiti_lista, strict=True)
        for indice, (casa, ospite) in enumerate(accoppiate):
            if _RIPOSA in (casa, ospite):
                continue
            # Alterna il fattore campo per non far giocare sempre in casa le
            # stesse squadre nei turni consecutivi.
            if (turno + indice) % 2:
                casa, ospite = ospite, casa
            partite.append(Partita(giornata=turno + 1, casa=casa, trasferta=ospite))

        ruota = [ruota[-1]] + ruota[:-1]

    if andata_ritorno:
        offset = len(elenco) - 1
        ritorno = [
            Partita(
                giornata=p.giornata + offset,
                casa=p.trasferta,
                trasferta=p.casa,
            )
            for p in partite
        ]
        partite.extend(ritorno)

    return Calendario(squadre=tuple(squadre), partite=tuple(partite))


def calcola_classifica(
    squadre: Sequence[str], partite: Sequence[Partita]
) -> list[RigaClassifica]:
    """Classifica ordinata: punti, differenza reti, gol fatti, punti fantacalcio."""
    tabella = {nome: RigaClassifica(squadra=nome) for nome in squadre}

    for partita in partite:
        if not partita.giocata:
            continue
        casa = tabella.get(partita.casa)
        trasferta = tabella.get(partita.trasferta)
        if casa is None or trasferta is None:
            raise ValueError(
                f"Partita con squadra sconosciuta: {partita.casa} - {partita.trasferta}"
            )

        casa.giocate += 1
        trasferta.giocate += 1
        casa.gol_fatti += partita.gol_casa
        casa.gol_subiti += partita.gol_trasferta
        trasferta.gol_fatti += partita.gol_trasferta
        trasferta.gol_subiti += partita.gol_casa
        casa.punti_fantacalcio += partita.punti_casa or 0.0
        trasferta.punti_fantacalcio += partita.punti_trasferta or 0.0

        if partita.gol_casa > partita.gol_trasferta:
            casa.vinte += 1
            trasferta.perse += 1
            casa.punti += PUNTI_VITTORIA
            trasferta.punti += PUNTI_SCONFITTA
        elif partita.gol_casa < partita.gol_trasferta:
            trasferta.vinte += 1
            casa.perse += 1
            trasferta.punti += PUNTI_VITTORIA
            casa.punti += PUNTI_SCONFITTA
        else:
            casa.pareggiate += 1
            trasferta.pareggiate += 1
            casa.punti += PUNTI_PAREGGIO
            trasferta.punti += PUNTI_PAREGGIO

    righe = list(tabella.values())
    righe.sort(
        key=lambda r: (
            r.punti,
            r.differenza_reti,
            r.gol_fatti,
            round(r.punti_fantacalcio, 2),
        ),
        reverse=True,
    )
    for riga in righe:
        riga.punti_fantacalcio = round(riga.punti_fantacalcio, 2)
    return righe
