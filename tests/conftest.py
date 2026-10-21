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
from collections.abc import Iterator
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
    italiano_u21: bool = False,
) -> Giocatore:
    return Giocatore(
        id=id_,
        nome=f"Giocatore {id_}",
        club="Club",
        ruoli=ruoli,
        ingaggio=ingaggio,
        nazionalita=nazionalita,
        italiano_u21=italiano_u21,
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
        giocatori[gid] = giocatore(
            gid, ruoli=ruoli, ingaggio=ingaggio, italiano_u21=indice < u21
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


# --- scrypt a costo da test -------------------------------------------------


@pytest.fixture(scope="session", autouse=True)
def scrypt_da_test() -> Iterator[int]:
    """Abbassa il costo di scrypt per tutta la sessione di test.

    In produzione `COSTO_N` sta a 2^14 di proposito: ~100 ms per verifica,
    impercettibili a chi entra e cari a chi tenta a forza bruta. Nei test
    quella lentezza e' tutto il costo: ogni `entra()` di un test dell'API e'
    una verifica, e i test dell'API ne fanno centinaia — era la voce piu'
    grossa della suite, piu' di tutto il resto insieme.

    Si abbassa **prima** che `modello_demo` costruisca il database, cosi' le
    cifrature finte e le verifiche usano lo stesso parametro: scrypt con un
    `n` diverso da' un digest diverso, e le password di demo non entrerebbero
    piu'. Il valore vero resta provato in `test_autenticazione`, che cifra e
    verifica senza passare da qui.

    Rende il costo vero, per chi deve rimetterlo: vedi `scrypt_di_produzione`.
    """
    from fantacalcio import autenticazione

    vero = autenticazione.COSTO_N
    autenticazione.COSTO_N = 2**4
    yield vero
    autenticazione.COSTO_N = vero


@pytest.fixture
def scrypt_di_produzione(scrypt_da_test: int, monkeypatch) -> None:
    """Rimette il costo vero di scrypt per la durata di un test.

    Serve a chi confronta un hash nato **in un altro processo** — uno script
    lanciato con `subprocess`, che il costo abbassato non lo vede: scrypt con
    un `n` diverso da' un digest diverso, e la verifica fallirebbe per il
    motivo sbagliato.
    """
    from fantacalcio import autenticazione

    monkeypatch.setattr(autenticazione, "COSTO_N", scrypt_da_test)


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
