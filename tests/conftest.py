"""Fabbriche condivise per costruire rose di prova."""

from __future__ import annotations

from datetime import date

import pytest

from fantacalcio.modelli import Contratto, Giocatore, Rosa, Squadra
from fantacalcio.regole import ParametriLega

DATA_DRAFT = date(2026, 9, 15)
STAGIONE = "2026/27"


def giocatore(
    id_: int,
    ruoli: tuple[str, ...] = ("C",),
    ingaggio: float = 3_000_000.0,
    nazionalita: str = "Italia",
    data_nascita: date | None = date(1996, 1, 1),
) -> Giocatore:
    return Giocatore(
        id=id_,
        nome=f"Giocatore {id_}",
        club="Club",
        ruoli=ruoli,
        ingaggio=ingaggio,
        nazionalita=nazionalita,
        data_nascita=data_nascita,
    )


def costruisci_rosa(
    squadra_id: int = 1,
    nome: str = "Tiri Team",
    dimensione: int = 30,
    annuali: int = 10,
    anni_altri: int = 2,
    portieri: int = 3,
    ingaggio: float = 3_000_000.0,
    u21: int = 0,
) -> Rosa:
    """Rosa conforme di default: 30 giocatori, 10 annuali, 50 anni, 90M di ingaggi.

    I parametri servono a rompere una regola alla volta nei test.
    """
    squadra = Squadra(id=squadra_id, nome=nome, fantallenatore="Mister")
    giocatori: dict[int, Giocatore] = {}
    contratti: list[Contratto] = []

    base = squadra_id * 1000
    for indice in range(dimensione):
        gid = base + indice
        ruoli = ("Por",) if indice < portieri else ("C",)
        # Gli Under 21 sono italiani nati dopo il compleanno-limite del draft.
        nascita = date(2007, 1, 1) if indice < u21 else date(1996, 1, 1)
        giocatori[gid] = giocatore(
            gid, ruoli=ruoli, ingaggio=ingaggio, data_nascita=nascita
        )
        contratti.append(
            Contratto(
                giocatore_id=gid,
                squadra_id=squadra_id,
                anni_residui=1 if indice < annuali else anni_altri,
            )
        )

    return Rosa(squadra=squadra, contratti=contratti).collega(giocatori)


@pytest.fixture
def parametri() -> ParametriLega:
    return ParametriLega()


@pytest.fixture
def rosa() -> Rosa:
    return costruisci_rosa()


@pytest.fixture
def classifica() -> list[str]:
    """Classifica della stagione precedente, dalla 1a alla 10a."""
    return [f"Squadra {i}" for i in range(1, 11)]
