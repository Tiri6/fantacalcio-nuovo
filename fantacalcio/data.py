"""Accesso ai dati: stesso set di funzioni sia su Supabase sia su SQLite demo.

Le pagine non sanno quale backend e' attivo: chiedono un `archivio()` e
ricevono DataFrame per le tabelle grezze oppure oggetti di dominio gia'
costruiti (`carica_rose`).
"""

from __future__ import annotations

import sqlite3
from dataclasses import dataclass
from datetime import date
from functools import lru_cache
from pathlib import Path

import pandas as pd

from .config import Impostazioni, carica_impostazioni
from .demo_data import costruisci_db
from .modelli import Contratto, Giocatore, Rosa, Squadra, VoceDeadMoney

TABELLE = ("squadre", "giocatori", "contratti", "dead_money", "calendario")


class Archivio:
    """Interfaccia comune ai backend."""

    nome: str = "sconosciuto"

    def tabella(self, nome: str) -> pd.DataFrame:  # pragma: no cover - astratto
        raise NotImplementedError

    def squadre(self) -> pd.DataFrame:
        return self.tabella("squadre")

    def giocatori(self) -> pd.DataFrame:
        return self.tabella("giocatori")

    def contratti(self) -> pd.DataFrame:
        return self.tabella("contratti")

    def dead_money(self) -> pd.DataFrame:
        return self.tabella("dead_money")

    def calendario(self) -> pd.DataFrame:
        return self.tabella("calendario")


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
# Dalle righe del database agli oggetti di dominio
# ---------------------------------------------------------------------------


def _data(valore) -> date | None:
    if valore is None or (isinstance(valore, float) and pd.isna(valore)):
        return None
    if isinstance(valore, date):
        return valore
    return date.fromisoformat(str(valore)[:10])


def carica_giocatori(arch: Archivio) -> dict[int, Giocatore]:
    """Anagrafica di tutti i giocatori della lega, indicizzata per id."""
    return {
        int(riga["id"]): Giocatore(
            id=int(riga["id"]),
            nome=riga["nome"],
            club=riga["club"],
            ruoli=tuple(str(riga["ruoli"]).split(";")),
            ingaggio=float(riga["ingaggio"]),
            nazionalita=riga["nazionalita"],
            data_nascita=_data(riga.get("data_nascita")),
        )
        for _, riga in arch.giocatori().iterrows()
    }


def carica_rose(arch: Archivio) -> dict[int, Rosa]:
    """Costruisce la rosa di ogni squadra, con contratti e Dead Money."""
    giocatori = carica_giocatori(arch)
    contratti = arch.contratti()
    voci_dead_money = arch.dead_money()

    rose: dict[int, Rosa] = {}
    for _, riga in arch.squadre().iterrows():
        squadra_id = int(riga["id"])
        squadra = Squadra(
            id=squadra_id,
            nome=riga["nome"],
            fantallenatore=riga["fantallenatore"],
        )

        suoi = contratti[contratti["squadra_id"] == squadra_id]
        suoi_contratti = [
            Contratto(
                giocatore_id=int(c["giocatore_id"]),
                squadra_id=squadra_id,
                anni_residui=int(c["anni_residui"]),
                prolungato=bool(c.get("prolungato", False)),
                stagione_prolungamento=(
                    c["stagione_prolungamento"]
                    if c.get("stagione_prolungamento")
                    and not pd.isna(c.get("stagione_prolungamento"))
                    else None
                ),
            )
            for _, c in suoi.iterrows()
        ]

        sue_voci = (
            voci_dead_money[voci_dead_money["squadra_id"] == squadra_id]
            if not voci_dead_money.empty
            else voci_dead_money
        )
        dead_money = [
            VoceDeadMoney(
                giocatore_id=(
                    int(v["giocatore_id"]) if not pd.isna(v["giocatore_id"]) else 0
                ),
                nome_giocatore=v["nome_giocatore"],
                importo=float(v["importo"]),
                stagione=v["stagione"],
                addebitato=bool(v.get("addebitato", False)),
            )
            for _, v in sue_voci.iterrows()
        ]

        rose[squadra_id] = Rosa(
            squadra=squadra, contratti=suoi_contratti, dead_money=dead_money
        ).collega(giocatori)

    return rose


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
