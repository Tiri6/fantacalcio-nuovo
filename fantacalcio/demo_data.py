"""Genera una lega di demo conforme al regolamento, su database SQLite.

Serve per avere il gestionale sempre avviabile senza credenziali: in una
sessione cloud si lancia l'app e c'e' gia' una lega con rose, contratti,
ingaggi e giornate giocate. Le rose sono costruite per rispettare monte anni,
regola "1/3", Salary Cap e Salary Floor: sono un banco di prova credibile.
"""

from __future__ import annotations

import random
import sqlite3
from datetime import date
from pathlib import Path

from .regole import ParametriLega
from .standings import genera_calendario

SEME = 20260915
STAGIONE = "2026/27"
DATA_DRAFT = date(2026, 9, 15)

SQUADRE = [
    ("Tiri Team", "Marco"),
    ("Padel United", "Luca"),
    ("Nuovo Cuneo FC", "Giulia"),
    ("Real Bisalta", "Andrea"),
    ("Gesso Rovers", "Francesca"),
    ("Stura Athletic", "Davide"),
    ("Borgo San Giuseppe", "Sara"),
    ("Atletico Madonna dell'Olmo", "Stefano"),
    ("Spinetta City", "Chiara"),
    ("Ronchi Wanderers", "Alberto"),
]

CLUB = [
    "Atalanta",
    "Bologna",
    "Cagliari",
    "Como",
    "Cremonese",
    "Fiorentina",
    "Genoa",
    "Inter",
    "Juventus",
    "Lazio",
    "Lecce",
    "Milan",
    "Napoli",
    "Parma",
    "Pisa",
    "Roma",
    "Sassuolo",
    "Torino",
    "Udinese",
    "Verona",
]

COGNOMI = [
    "Rossi",
    "Bianchi",
    "Esposito",
    "Romano",
    "Colombo",
    "Ricci",
    "Marino",
    "Greco",
    "Bruno",
    "Gallo",
    "Conti",
    "De Luca",
    "Mancini",
    "Costa",
    "Giordano",
    "Rizzo",
    "Lombardi",
    "Moretti",
    "Barbieri",
    "Fontana",
    "Santoro",
    "Mariani",
    "Rinaldi",
    "Caruso",
    "Ferrara",
    "Galli",
    "Martini",
    "Leone",
    "Longo",
    "Gentile",
    "Martinelli",
    "Vitale",
    "Lombardo",
    "Serra",
    "Coppola",
    "De Santis",
    "D'Angelo",
    "Marchetti",
    "Parisi",
    "Villa",
    "Sanna",
    "Farina",
    "Rizzi",
    "Monti",
    "Cattaneo",
    "Morelli",
    "Amato",
    "Silvestri",
    "Mazza",
    "Testa",
    "Grassi",
    "Pellegrini",
    "Palumbo",
]

NAZIONI = ["Italia"] * 6 + ["Argentina", "Francia", "Brasile", "Serbia", "Olanda"]

# Ruoli Mantra realistici per la costruzione della rosa: 3 portieri, poi
# difensori, centrocampisti e attaccanti in proporzioni sensate.
IMPIANTO_RUOLI = (
    [("Por",)] * 3
    + [("Dc",)] * 5
    + [("Dd", "E")] * 2
    + [("Ds", "E")] * 2
    + [("M", "C")] * 3
    + [("C",)] * 3
    + [("E", "W")] * 2
    + [("W", "T")] * 3
    + [("T", "A")] * 2
    + [("A", "Pc")] * 3
    + [("Pc",)] * 3
)

DIMENSIONE_ROSA = 31
GIORNATE_GIOCATE = 11

# Squadre che nella demo mostrano regole specifiche del regolamento:
# rosa ampliata dagli Under 21 (art. 2) e Dead Money da svincolo (art. 7).
ROSE_AMPLIATE = {3: 34, 6: 35}
SQUADRE_CON_DEAD_MONEY = (2, 5, 8)


def _impianto_ruoli(dimensione: int) -> list[tuple[str, ...]]:
    """Ruoli Mantra per una rosa di quella dimensione, portieri sempre 3."""
    ruoli = list(IMPIANTO_RUOLI)
    riempitivi = [("C",), ("Dc",), ("W", "T"), ("A",), ("M", "C")]
    indice = 0
    while len(ruoli) < dimensione:
        ruoli.append(riempitivi[indice % len(riempitivi)])
        indice += 1
    return ruoli[:dimensione]


def _durate(dimensione: int) -> list[int]:
    """Contratti che rispettano insieme la regola "1/3" e il monte anni.

    Si parte dagli annuali richiesti, si mettono tutti gli altri a 2 anni e si
    alza a 3 finche' il monte anni lo consente: cosi' la rosa e' realistica e
    non lascia anni inutilizzati.
    """
    parametri = ParametriLega()
    annuali = parametri.minimo_annuali(dimensione)
    restanti = dimensione - annuali
    budget = parametri.monte_anni - annuali

    if restanti * 2 > budget:
        raise ValueError(
            f"Una rosa da {dimensione} non entra nel monte anni di "
            f"{parametri.monte_anni}: servirebbero almeno {annuali + restanti * 2} anni"
        )

    da_alzare = min(restanti, budget - restanti * 2)
    durate = [1] * annuali + [3] * da_alzare + [2] * (restanti - da_alzare)

    assert len(durate) == dimensione
    assert sum(durate) <= parametri.monte_anni
    return durate


def _ingaggi(rng: random.Random, quanti: int, totale: float) -> list[float]:
    """Ingaggi casuali riscalati per sommare esattamente al totale voluto.

    Cosi' ogni squadra nasce dentro la forbice Salary Floor - Salary Cap.
    """
    grezzi = [max(0.4, rng.lognormvariate(0.6, 0.7)) for _ in range(quanti)]
    fattore = totale / sum(grezzi)
    return [round(v * fattore, -4) for v in grezzi]


def _data_nascita(rng: random.Random, under21: bool) -> date:
    if under21:
        # Under 21 al draft di Settembre 2026: nato dopo il 15/09/2005.
        return date(rng.randint(2006, 2008), rng.randint(1, 12), rng.randint(1, 28))
    return date(rng.randint(1990, 2003), rng.randint(1, 12), rng.randint(1, 28))


def genera_lega(rng: random.Random | None = None) -> dict:
    """Costruisce squadre, giocatori, contratti, dead money e calendario."""
    rng = rng or random.Random(SEME)
    parametri = ParametriLega()

    squadre = [
        {"id": i + 1, "nome": nome, "fantallenatore": mister}
        for i, (nome, mister) in enumerate(SQUADRE)
    ]

    giocatori: list[dict] = []
    contratti: list[dict] = []
    dead_money: list[dict] = []
    id_giocatore = 1

    for squadra in squadre:
        dimensione = ROSE_AMPLIATE.get(squadra["id"], DIMENSIONE_ROSA)
        durate = _durate(dimensione)
        # Ogni squadra spende tra 84M e 97M: dentro la forbice, ma non tutte uguali.
        totale_ingaggi = rng.uniform(84, 97) * 1_000_000
        ingaggi = _ingaggi(rng, dimensione, totale_ingaggi)
        # Chi ha la rosa ampliata deve avere gli Under 21 che la giustificano.
        quanti_u21 = max(
            dimensione - parametri.rosa_massimo_base, rng.choice([0, 1, 1, 2])
        )

        assegnazioni = list(
            zip(_impianto_ruoli(dimensione), durate, ingaggi, strict=True)
        )
        rng.shuffle(assegnazioni)

        for indice, (ruoli, anni, ingaggio) in enumerate(assegnazioni):
            under21 = indice < quanti_u21
            nazionalita = "Italia" if under21 else rng.choice(NAZIONI)
            giocatori.append(
                {
                    "id": id_giocatore,
                    "nome": f"{rng.choice(COGNOMI)} ({id_giocatore})",
                    "club": rng.choice(CLUB),
                    "ruoli": ";".join(ruoli),
                    "ingaggio": ingaggio,
                    "nazionalita": nazionalita,
                    "data_nascita": _data_nascita(rng, under21).isoformat(),
                }
            )
            contratti.append(
                {
                    "giocatore_id": id_giocatore,
                    "squadra_id": squadra["id"],
                    "anni_residui": anni,
                    "prolungato": 0,
                    "stagione_prolungamento": None,
                }
            )
            id_giocatore += 1

        # Alcune squadre si portano dietro il Dead Money di uno svincolo.
        if squadra["id"] in SQUADRE_CON_DEAD_MONEY:
            residuo = rng.choice([1, 2, 3])
            ingaggio_tagliato = rng.uniform(1.5, 4.5) * 1_000_000
            dead_money.append(
                {
                    "squadra_id": squadra["id"],
                    "giocatore_id": None,
                    "nome_giocatore": f"{rng.choice(COGNOMI)} (svincolato)",
                    "importo": round(
                        parametri.quota_dead_money * ingaggio_tagliato * residuo, -4
                    ),
                    "stagione": STAGIONE,
                    "addebitato": 0,
                }
            )

    calendario = _genera_calendario(squadre, rng)
    return {
        "squadre": squadre,
        "giocatori": giocatori,
        "contratti": contratti,
        "dead_money": dead_money,
        "calendario": calendario,
    }


def _genera_calendario(squadre: list[dict], rng: random.Random) -> list[dict]:
    """Calendario andata/ritorno con i risultati delle giornate gia' disputate.

    I punteggi arrivano da Leghe Fantacalcio: qui si simulano soltanto, perche'
    il gestionale li importa e non li calcola.
    """
    indice = {s["nome"]: s["id"] for s in squadre}
    partite = genera_calendario([s["nome"] for s in squadre]).partite
    parametri = ParametriLega()

    righe = []
    for numero, partita in enumerate(partite, start=1):
        riga = {
            "id": numero,
            "giornata": partita.giornata,
            "casa_id": indice[partita.casa],
            "trasferta_id": indice[partita.trasferta],
            "gol_casa": None,
            "gol_trasferta": None,
            "punti_casa": None,
            "punti_trasferta": None,
        }
        if partita.giornata <= GIORNATE_GIOCATE:
            from .regole import fasce_gol

            punti_casa = round(rng.gauss(66, 6) * 2) / 2
            punti_trasferta = round(rng.gauss(66, 6) * 2) / 2
            riga.update(
                punti_casa=punti_casa,
                punti_trasferta=punti_trasferta,
                gol_casa=fasce_gol(punti_casa, parametri),
                gol_trasferta=fasce_gol(punti_trasferta, parametri),
            )
        righe.append(riga)
    return righe


SCHEMA_SQLITE = """
create table if not exists squadre (
    id integer primary key,
    nome text not null unique,
    fantallenatore text not null
);
create table if not exists giocatori (
    id integer primary key,
    nome text not null,
    club text not null,
    ruoli text not null,
    ingaggio real not null,
    nazionalita text not null,
    data_nascita text
);
create table if not exists contratti (
    giocatore_id integer primary key,
    squadra_id integer not null,
    anni_residui integer not null,
    prolungato integer not null default 0,
    stagione_prolungamento text
);
create table if not exists dead_money (
    id integer primary key autoincrement,
    squadra_id integer not null,
    giocatore_id integer,
    nome_giocatore text not null,
    importo real not null,
    stagione text not null,
    addebitato integer not null default 0
);
create table if not exists calendario (
    id integer primary key,
    giornata integer not null,
    casa_id integer not null,
    trasferta_id integer not null,
    gol_casa integer,
    gol_trasferta integer,
    punti_casa real,
    punti_trasferta real
);
"""


def costruisci_db(percorso: Path, forza: bool = False) -> Path:
    """Crea (se serve) il database di demo e lo popola."""
    percorso = Path(percorso)
    if percorso.exists() and not forza:
        return percorso

    percorso.parent.mkdir(parents=True, exist_ok=True)
    percorso.unlink(missing_ok=True)
    lega = genera_lega()

    def inserisci(conn, tabella: str, righe: list[dict]) -> None:
        if not righe:
            return
        colonne = list(righe[0])
        conn.executemany(
            f"insert into {tabella} ({', '.join(colonne)}) "
            f"values ({', '.join(':' + c for c in colonne)})",
            righe,
        )

    with sqlite3.connect(percorso) as conn:
        conn.executescript(SCHEMA_SQLITE)
        for tabella in ("squadre", "giocatori", "contratti", "calendario"):
            inserisci(conn, tabella, lega[tabella])
        inserisci(conn, "dead_money", lega["dead_money"])

    return percorso


if __name__ == "__main__":  # pragma: no cover
    from .config import DB_DEMO

    print(f"Database di demo creato in {costruisci_db(DB_DEMO, forza=True)}")
