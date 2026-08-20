"""Genera un database SQLite di demo con una lega completa.

Serve per avere l'app sempre avviabile senza credenziali Supabase: in una
sessione cloud si lancia `streamlit run app.py` e c'e' gia' una lega con
classifica, rose e giornate giocate.
"""

from __future__ import annotations

import random
import sqlite3
from pathlib import Path

from .scoring import Prestazione, RegoleLega, calcola_formazione
from .standings import genera_calendario

SEME = 20240801

NOMI_SQUADRE = [
    ("Real Sporcaccioni", "Marco"),
    ("Atletico Divano", "Luca"),
    ("Bayern Monello", "Giulia"),
    ("Deportivo La Pennica", "Andrea"),
    ("Manchester Sitty", "Francesca"),
    ("Inzaghi Boys", "Davide"),
    ("Ajax di Casa", "Sara"),
    ("Borussia Mokakoffen", "Stefano"),
]

CLUB = [
    "Atalanta", "Bologna", "Cagliari", "Como", "Fiorentina", "Genoa",
    "Inter", "Juventus", "Lazio", "Lecce", "Milan", "Napoli",
    "Parma", "Roma", "Torino", "Udinese", "Venezia", "Verona",
]

COGNOMI = [
    "Rossi", "Bianchi", "Esposito", "Romano", "Colombo", "Ricci", "Marino",
    "Greco", "Bruno", "Gallo", "Conti", "De Luca", "Mancini", "Costa",
    "Giordano", "Rizzo", "Lombardi", "Moretti", "Barbieri", "Fontana",
    "Santoro", "Mariani", "Rinaldi", "Caruso", "Ferrara", "Galli", "Martini",
    "Leone", "Longo", "Gentile", "Martinelli", "Vitale", "Lombardo", "Serra",
    "Coppola", "De Santis", "D'Angelo", "Marchetti", "Parisi", "Villa",
    "Sanna", "Farina", "Rizzi", "Monti", "Cattaneo", "Morelli", "Amato",
    "Silvestri", "Mazza", "Testa", "Grassi", "Pellegrini", "Palumbo",
    "Sorrentino", "Basile", "Neri", "Bernardi", "Milani", "Piras", "Rossetti",
]

# Composizione della rosa per ruolo.
ROSA = {"P": 3, "D": 8, "C": 8, "A": 6}
# Modulo dei titolari (1 portiere + 4 difensori + 4 centrocampisti + 2 attaccanti).
MODULO = {"P": 1, "D": 4, "C": 4, "A": 2}

GIORNATE_GIOCATE = 6

SCHEMA_SQLITE = """
create table if not exists squadre (
    id integer primary key,
    nome text not null unique,
    allenatore text not null,
    crediti integer not null default 500
);
create table if not exists giocatori (
    id integer primary key,
    nome text not null,
    ruolo text not null,
    club text not null,
    quotazione integer not null default 1
);
create table if not exists rose (
    squadra_id integer not null,
    giocatore_id integer not null,
    prezzo integer not null default 1,
    primary key (squadra_id, giocatore_id)
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
create table if not exists prestazioni (
    giornata integer not null,
    giocatore_id integer not null,
    voto real,
    gol_segnati integer not null default 0,
    gol_su_rigore integer not null default 0,
    rigori_sbagliati integer not null default 0,
    rigori_parati integer not null default 0,
    gol_subiti integer not null default 0,
    autogol integer not null default 0,
    assist integer not null default 0,
    ammonizioni integer not null default 0,
    espulsioni integer not null default 0,
    primary key (giornata, giocatore_id)
);
create table if not exists formazioni (
    giornata integer not null,
    squadra_id integer not null,
    giocatore_id integer not null,
    titolare integer not null default 0,
    ordine_panchina integer not null default 0,
    primary key (giornata, squadra_id, giocatore_id)
);
"""


def _genera_giocatori(rng: random.Random) -> list[dict]:
    """Un pool di giocatori grande abbastanza per tutte le rose."""
    per_squadra = sum(ROSA.values())
    totale_per_ruolo = {r: n * len(NOMI_SQUADRE) for r, n in ROSA.items()}

    giocatori: list[dict] = []
    id_corrente = 1
    for ruolo, quanti in totale_per_ruolo.items():
        for indice in range(quanti):
            cognome = COGNOMI[(id_corrente * 7 + indice) % len(COGNOMI)]
            giocatori.append(
                {
                    "id": id_corrente,
                    # Il suffisso evita omonimie tra i 200 giocatori generati.
                    "nome": f"{cognome} ({ruolo}{indice + 1})",
                    "ruolo": ruolo,
                    "club": CLUB[id_corrente % len(CLUB)],
                    "quotazione": max(1, int(rng.gauss(12 if ruolo == "A" else 8, 5))),
                }
            )
            id_corrente += 1

    assert len(giocatori) == per_squadra * len(NOMI_SQUADRE)
    return giocatori


def _assegna_rose(giocatori: list[dict], rng: random.Random) -> list[dict]:
    """Distribuisce i giocatori tra le squadre rispettando la composizione rosa."""
    per_ruolo: dict[str, list[dict]] = {r: [] for r in ROSA}
    for g in giocatori:
        per_ruolo[g["ruolo"]].append(g)
    for elenco in per_ruolo.values():
        rng.shuffle(elenco)

    rose: list[dict] = []
    for indice_squadra in range(len(NOMI_SQUADRE)):
        squadra_id = indice_squadra + 1
        for ruolo, quanti in ROSA.items():
            for _ in range(quanti):
                giocatore = per_ruolo[ruolo].pop()
                prezzo = max(1, giocatore["quotazione"] + rng.randint(-3, 8))
                rose.append(
                    {
                        "squadra_id": squadra_id,
                        "giocatore_id": giocatore["id"],
                        "prezzo": prezzo,
                    }
                )
    return rose


def _genera_prestazione(giocatore: dict, giornata: int, rng: random.Random) -> dict:
    """Una prestazione plausibile: qualche s.v., bonus in base al ruolo."""
    ruolo = giocatore["ruolo"]

    if rng.random() < 0.18:  # infortunato / non convocato
        return {
            "giornata": giornata,
            "giocatore_id": giocatore["id"],
            "voto": None,
        }

    voto = round(min(10.0, max(4.0, rng.gauss(6.0, 0.8))) * 2) / 2
    dati = {
        "giornata": giornata,
        "giocatore_id": giocatore["id"],
        "voto": voto,
        "ammonizioni": 1 if rng.random() < 0.12 else 0,
        "espulsioni": 1 if rng.random() < 0.015 else 0,
    }

    probabilita_gol = {"P": 0.0, "D": 0.05, "C": 0.12, "A": 0.28}[ruolo]
    if rng.random() < probabilita_gol:
        dati["gol_segnati"] = 1
    if rng.random() < {"P": 0.0, "D": 0.06, "C": 0.15, "A": 0.12}[ruolo]:
        dati["assist"] = 1
    if ruolo == "P":
        dati["gol_subiti"] = rng.choice([0, 0, 1, 1, 1, 2, 2, 3])
        if rng.random() < 0.05:
            dati["rigori_parati"] = 1
    if rng.random() < 0.01:
        dati["autogol"] = 1

    return dati


def _formazione(rosa_squadra: list[dict], rng: random.Random) -> tuple[list, list]:
    """Sceglie titolari secondo il modulo; il resto va in panchina, ordinato."""
    per_ruolo: dict[str, list[dict]] = {r: [] for r in ROSA}
    for g in rosa_squadra:
        per_ruolo[g["ruolo"]].append(g)
    for elenco in per_ruolo.values():
        rng.shuffle(elenco)

    titolari: list[dict] = []
    panchina: list[dict] = []
    for ruolo, quanti in MODULO.items():
        titolari.extend(per_ruolo[ruolo][:quanti])
        panchina.extend(per_ruolo[ruolo][quanti:])

    rng.shuffle(panchina)
    return titolari, panchina


def _a_prestazione(giocatore: dict, riga: dict) -> Prestazione:
    return Prestazione(
        giocatore_id=giocatore["id"],
        nome=giocatore["nome"],
        ruolo=giocatore["ruolo"],
        voto=riga.get("voto"),
        gol_segnati=riga.get("gol_segnati", 0),
        gol_su_rigore=riga.get("gol_su_rigore", 0),
        rigori_sbagliati=riga.get("rigori_sbagliati", 0),
        rigori_parati=riga.get("rigori_parati", 0),
        gol_subiti=riga.get("gol_subiti", 0),
        autogol=riga.get("autogol", 0),
        assist=riga.get("assist", 0),
        ammonizioni=riga.get("ammonizioni", 0),
        espulsioni=riga.get("espulsioni", 0),
    )


def costruisci_db(percorso: Path, forza: bool = False) -> Path:
    """Crea (se serve) il DB di demo e lo popola. Restituisce il percorso."""
    percorso = Path(percorso)
    if percorso.exists() and not forza:
        return percorso

    percorso.parent.mkdir(parents=True, exist_ok=True)
    if percorso.exists():
        percorso.unlink()

    rng = random.Random(SEME)
    regole = RegoleLega()

    giocatori = _genera_giocatori(rng)
    per_id = {g["id"]: g for g in giocatori}
    rose = _assegna_rose(giocatori, rng)

    rosa_per_squadra: dict[int, list[dict]] = {}
    for riga in rose:
        rosa_per_squadra.setdefault(riga["squadra_id"], []).append(
            per_id[riga["giocatore_id"]]
        )

    calendario = genera_calendario([n for n, _ in NOMI_SQUADRE])
    indice_squadra = {nome: i + 1 for i, (nome, _) in enumerate(NOMI_SQUADRE)}

    prestazioni: list[dict] = []
    formazioni: list[dict] = []
    punteggi: dict[tuple[int, int], tuple[float, int]] = {}

    for giornata in range(1, GIORNATE_GIOCATE + 1):
        per_giornata = {
            g["id"]: _genera_prestazione(g, giornata, rng) for g in giocatori
        }
        prestazioni.extend(per_giornata.values())

        for squadra_id, rosa_squadra in rosa_per_squadra.items():
            titolari, panchina = _formazione(rosa_squadra, rng)
            for g in titolari:
                formazioni.append(
                    {
                        "giornata": giornata,
                        "squadra_id": squadra_id,
                        "giocatore_id": g["id"],
                        "titolare": 1,
                        "ordine_panchina": 0,
                    }
                )
            for ordine, g in enumerate(panchina, start=1):
                formazioni.append(
                    {
                        "giornata": giornata,
                        "squadra_id": squadra_id,
                        "giocatore_id": g["id"],
                        "titolare": 0,
                        "ordine_panchina": ordine,
                    }
                )

            risultato = calcola_formazione(
                [_a_prestazione(g, per_giornata[g["id"]]) for g in titolari],
                [_a_prestazione(g, per_giornata[g["id"]]) for g in panchina],
                regole,
            )
            punteggi[(giornata, squadra_id)] = (risultato.totale, risultato.gol)

    righe_calendario = []
    for indice, partita in enumerate(calendario.partite, start=1):
        casa_id = indice_squadra[partita.casa]
        trasferta_id = indice_squadra[partita.trasferta]
        riga = {
            "id": indice,
            "giornata": partita.giornata,
            "casa_id": casa_id,
            "trasferta_id": trasferta_id,
            "gol_casa": None,
            "gol_trasferta": None,
            "punti_casa": None,
            "punti_trasferta": None,
        }
        if partita.giornata <= GIORNATE_GIOCATE:
            punti_casa, gol_casa = punteggi[(partita.giornata, casa_id)]
            punti_trasferta, gol_trasferta = punteggi[(partita.giornata, trasferta_id)]
            riga.update(
                gol_casa=gol_casa,
                gol_trasferta=gol_trasferta,
                punti_casa=punti_casa,
                punti_trasferta=punti_trasferta,
            )
        righe_calendario.append(riga)

    with sqlite3.connect(percorso) as conn:
        conn.executescript(SCHEMA_SQLITE)
        conn.executemany(
            "insert into squadre (id, nome, allenatore, crediti) values (?, ?, ?, ?)",
            [(i + 1, nome, mister, 500) for i, (nome, mister) in enumerate(NOMI_SQUADRE)],
        )
        conn.executemany(
            "insert into giocatori (id, nome, ruolo, club, quotazione)"
            " values (:id, :nome, :ruolo, :club, :quotazione)",
            giocatori,
        )
        conn.executemany(
            "insert into rose (squadra_id, giocatore_id, prezzo)"
            " values (:squadra_id, :giocatore_id, :prezzo)",
            rose,
        )
        conn.executemany(
            "insert into calendario (id, giornata, casa_id, trasferta_id,"
            " gol_casa, gol_trasferta, punti_casa, punti_trasferta)"
            " values (:id, :giornata, :casa_id, :trasferta_id,"
            " :gol_casa, :gol_trasferta, :punti_casa, :punti_trasferta)",
            righe_calendario,
        )
        colonne = [
            "giornata",
            "giocatore_id",
            "voto",
            "gol_segnati",
            "gol_su_rigore",
            "rigori_sbagliati",
            "rigori_parati",
            "gol_subiti",
            "autogol",
            "assist",
            "ammonizioni",
            "espulsioni",
        ]
        conn.executemany(
            f"insert into prestazioni ({', '.join(colonne)})"
            f" values ({', '.join(':' + c for c in colonne)})",
            [
                # `voto` puo' essere None (s.v.); gli altri campi mancanti sono 0.
                {c: p.get("voto") if c == "voto" else p.get(c, 0) for c in colonne}
                for p in prestazioni
            ],
        )
        conn.executemany(
            "insert into formazioni (giornata, squadra_id, giocatore_id,"
            " titolare, ordine_panchina)"
            " values (:giornata, :squadra_id, :giocatore_id,"
            " :titolare, :ordine_panchina)",
            formazioni,
        )

    return percorso


if __name__ == "__main__":  # pragma: no cover
    from .config import DB_DEMO

    destinazione = costruisci_db(DB_DEMO, forza=True)
    print(f"Database di demo creato in {destinazione}")
