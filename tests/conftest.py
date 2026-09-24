"""Fabbriche condivise: rose di prova e il database di demo.

Il database di demo si costruisce **una volta per sessione** e poi si copia.
Non e' un vezzo: costruirlo costa 0,40 s, di cui 0,35 sono le dieci cifrature
scrypt degli utenti finti — e scrypt e' caro di proposito. Sessantasette test
lo ricostruivano da zero: settecentoquarantatre cifrature in tutto, e
trentatre secondi su quarantasei di suite spesi a cifrare sempre le stesse
dieci password. Adesso le cifrature sono centotrentatre e la suite dura nove
secondi.

Copiare il file (128 KB) costa 0,08 ms, e ogni test lavora sulla sua copia,
quindi resta isolato esattamente come prima. Chi invece deve provare **la
costruzione** — che il database vecchio si rigeneri, che quello buono non si
tocchi — continua a chiamare il costruttore vero: sono tre test in
`test_data.py`, e sono l'unico posto dove quel codice va esercitato.
"""

from __future__ import annotations

import shutil
from datetime import date
from pathlib import Path

import pytest

from fantacalcio.data import ArchivioSQLite
from fantacalcio.demo_data import costruisci_db
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
    squadra = Squadra(id=squadra_id, nome=nome, presidente="Mister")
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


# --- il database di demo ----------------------------------------------------


@pytest.fixture(scope="session")
def modello_demo(tmp_path_factory) -> Path:
    """Il database di demo, costruito una volta sola per tutta la sessione.

    Non si usa direttamente nei test: e' il calco da cui `db_demo` ritaglia
    una copia. Scriverci sopra sporcherebbe tutti i test che vengono dopo.
    """
    percorso = tmp_path_factory.mktemp("modello-demo") / "demo.db"
    costruisci_db(percorso)
    return percorso


@pytest.fixture
def db_demo(modello_demo: Path, tmp_path: Path) -> Path:
    """Una copia fresca del database di demo, tutta per questo test."""
    copia = tmp_path / "demo.db"
    shutil.copy(modello_demo, copia)
    return copia


@pytest.fixture
def archivio_demo(db_demo: Path) -> ArchivioSQLite:
    """Un archivio sul database di demo: dieci squadre, il listone, il calendario.

    Aprirlo non ricostruisce niente — il file e' gia' allineato allo schema —
    quindi costa mezzo millesimo di secondo invece di quattro decimi.
    """
    return ArchivioSQLite(db_demo)


@pytest.fixture(scope="module")
def archivio_demo_del_modulo(modello_demo: Path, tmp_path_factory) -> ArchivioSQLite:
    """Come `archivio_demo`, ma una copia sola per tutto il modulo.

    Serve a chi legge e non scrive — le tabelle di `vista`, per esempio — e
    deve farlo da una fixture a sua volta di modulo, che non puo' dipendere
    da una di funzione.
    """
    copia = tmp_path_factory.mktemp("demo-modulo") / "demo.db"
    shutil.copy(modello_demo, copia)
    return ArchivioSQLite(copia)
