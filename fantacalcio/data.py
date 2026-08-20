"""Accesso ai dati: stesso set di funzioni sia su Supabase sia su SQLite demo.

Le pagine Streamlit non sanno quale backend e' attivo: chiedono un
`archivio()` e ricevono DataFrame con le stesse colonne.
"""

from __future__ import annotations

import sqlite3
from dataclasses import dataclass
from functools import lru_cache
from pathlib import Path

import pandas as pd

from .config import Impostazioni, carica_impostazioni
from .demo_data import costruisci_db

TABELLE = ("squadre", "giocatori", "rose", "calendario", "prestazioni", "formazioni")


class Archivio:
    """Interfaccia comune ai backend."""

    nome: str = "sconosciuto"

    def tabella(self, nome: str) -> pd.DataFrame:  # pragma: no cover - astratto
        raise NotImplementedError

    def squadre(self) -> pd.DataFrame:
        return self.tabella("squadre")

    def giocatori(self) -> pd.DataFrame:
        return self.tabella("giocatori")

    def rose(self) -> pd.DataFrame:
        return self.tabella("rose")

    def calendario(self) -> pd.DataFrame:
        return self.tabella("calendario")

    def prestazioni(self) -> pd.DataFrame:
        return self.tabella("prestazioni")

    def formazioni(self) -> pd.DataFrame:
        return self.tabella("formazioni")


@dataclass
class ArchivioSQLite(Archivio):
    percorso: Path
    nome: str = "demo (SQLite)"

    def __post_init__(self) -> None:
        costruisci_db(self.percorso)

    def tabella(self, nome: str) -> pd.DataFrame:
        if nome not in TABELLE:
            raise ValueError(f"Tabella non prevista: {nome}")
        with sqlite3.connect(self.percorso) as conn:
            return pd.read_sql_query(f"select * from {nome}", conn)


@dataclass
class ArchivioSupabase(Archivio):
    url: str
    key: str
    nome: str = "Supabase"

    def __post_init__(self) -> None:
        from supabase import create_client

        self._client = create_client(self.url.rstrip("/"), self.key)

    def tabella(self, nome: str) -> pd.DataFrame:
        if nome not in TABELLE:
            raise ValueError(f"Tabella non prevista: {nome}")
        risposta = self._client.table(nome).select("*").execute()
        return pd.DataFrame(risposta.data or [])


def crea_archivio(impostazioni: Impostazioni | None = None) -> Archivio:
    """Sceglie il backend: Supabase se ci sono le credenziali, altrimenti demo."""
    impostazioni = impostazioni or carica_impostazioni()
    if impostazioni.usa_supabase:
        return ArchivioSupabase(impostazioni.supabase_url, impostazioni.supabase_key)
    return ArchivioSQLite(impostazioni.percorso_db_demo)


@lru_cache(maxsize=1)
def archivio() -> Archivio:
    """Istanza condivisa: evita di riaprire la connessione a ogni rerun."""
    return crea_archivio()


# ---------------------------------------------------------------------------
# Viste derivate, usate direttamente dalle pagine
# ---------------------------------------------------------------------------


def rose_dettagliate(arch: Archivio) -> pd.DataFrame:
    """Rose con nome squadra, nome giocatore, ruolo, club, prezzo."""
    squadre = arch.squadre().rename(columns={"id": "squadra_id", "nome": "squadra"})
    giocatori = arch.giocatori().rename(
        columns={"id": "giocatore_id", "nome": "giocatore"}
    )
    unione = (
        arch.rose()
        .merge(squadre[["squadra_id", "squadra", "allenatore"]], on="squadra_id")
        .merge(
            giocatori[["giocatore_id", "giocatore", "ruolo", "club", "quotazione"]],
            on="giocatore_id",
        )
    )
    ordine = {r: i for i, r in enumerate(("P", "D", "C", "A"))}
    unione["_ordine"] = unione["ruolo"].map(ordine)
    return (
        unione.sort_values(
            ["squadra", "_ordine", "prezzo"], ascending=[True, True, False]
        )
        .drop(columns="_ordine")
        .reset_index(drop=True)
    )


def calendario_dettagliato(arch: Archivio) -> pd.DataFrame:
    """Calendario con i nomi delle squadre al posto degli id."""
    squadre = arch.squadre()[["id", "nome"]]
    partite = (
        arch.calendario()
        .merge(squadre.rename(columns={"id": "casa_id", "nome": "casa"}), on="casa_id")
        .merge(
            squadre.rename(columns={"id": "trasferta_id", "nome": "trasferta"}),
            on="trasferta_id",
        )
    )
    return partite.sort_values(["giornata", "casa"]).reset_index(drop=True)


def prestazioni_dettagliate(arch: Archivio) -> pd.DataFrame:
    """Prestazioni arricchite con giocatore, ruolo, club e squadra di fantacalcio."""
    giocatori = arch.giocatori().rename(
        columns={"id": "giocatore_id", "nome": "giocatore"}
    )
    squadre = arch.squadre().rename(columns={"id": "squadra_id", "nome": "squadra"})
    rose = arch.rose()[["squadra_id", "giocatore_id"]]

    return (
        arch.prestazioni()
        .merge(
            giocatori[["giocatore_id", "giocatore", "ruolo", "club"]],
            on="giocatore_id",
        )
        .merge(rose, on="giocatore_id", how="left")
        .merge(squadre[["squadra_id", "squadra"]], on="squadra_id", how="left")
    )
