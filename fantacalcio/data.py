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
from typing import TYPE_CHECKING

import pandas as pd

from .config import Impostazioni, carica_impostazioni
from .demo_data import costruisci_db
from .identita import IdentitaSquadra, StileMaglia
from .modelli import Contratto, Giocatore, Rosa, Squadra, VoceDeadMoney

if TYPE_CHECKING:  # pragma: no cover - solo per i type checker
    from .autenticazione import Credenziali

TABELLE = (
    "squadre",
    "giocatori",
    "contratti",
    "dead_money",
    "calendario",
    "utenti",
    "scambi",
    "scambi_movimenti",
)


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

    def scrivi(
        self, nome: str, righe: list[dict], chiave: str
    ) -> int:  # pragma: no cover - astratto
        """Inserisce o aggiorna righe, usando `chiave` per riconoscere i duplicati."""
        raise NotImplementedError

    def svuota(self, nome: str) -> None:  # pragma: no cover - astratto
        raise NotImplementedError


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

    def scrivi(self, nome: str, righe: list[dict], chiave: str) -> int:
        if nome not in TABELLE:
            raise ValueError(f"Tabella non prevista: {nome}")
        if not righe:
            return 0

        colonne = list(righe[0])
        if chiave not in colonne:
            raise ValueError(
                f"La chiave '{chiave}' non e' tra le colonne scritte: {colonne}"
            )
        with sqlite3.connect(self.percorso) as conn:
            conn.executemany(
                f"insert or replace into {nome} ({', '.join(colonne)}) "
                f"values ({', '.join(':' + c for c in colonne)})",
                righe,
            )
        return len(righe)

    def svuota(self, nome: str) -> None:
        if nome not in TABELLE:
            raise ValueError(f"Tabella non prevista: {nome}")
        with sqlite3.connect(self.percorso) as conn:
            conn.execute(f"delete from {nome}")


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

    def scrivi(self, nome: str, righe: list[dict], chiave: str) -> int:
        if nome not in TABELLE:
            raise ValueError(f"Tabella non prevista: {nome}")
        if not righe:
            return 0
        # Serve la service key: con la chiave anon la RLS blocca le scritture.
        self._client.table(nome).upsert(righe, on_conflict=chiave).execute()
        return len(righe)

    def svuota(self, nome: str) -> None:
        if nome not in TABELLE:
            raise ValueError(f"Tabella non prevista: {nome}")
        self._client.table(nome).delete().neq("id", -1).execute()


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


def _testo(valore, predefinito: str = "") -> str:
    if valore is None or (isinstance(valore, float) and pd.isna(valore)):
        return predefinito
    return str(valore)


def costruisci_squadra(riga) -> Squadra:
    """Da una riga della tabella `squadre` all'oggetto di dominio.

    I campi di identita' sono tutti opzionali: una lega appena creata ha solo
    nome e presidente, e il resto si compila dalla pagina Identita'.
    """
    stile = _testo(riga.get("stile_maglia"), "TINTA_UNITA")
    try:
        stile_maglia = StileMaglia[stile]
    except KeyError:
        stile_maglia = StileMaglia.TINTA_UNITA

    anno = riga.get("anno_fondazione")
    identita = IdentitaSquadra(
        presidente=_testo(riga.get("presidente")),
        motto=_testo(riga.get("motto")),
        stadio=_testo(riga.get("stadio")),
        colore_primario=_testo(riga.get("colore_primario"), "#2e7d32"),
        colore_secondario=_testo(riga.get("colore_secondario"), "#ffffff"),
        stile_maglia=stile_maglia,
        logo=_testo(riga.get("logo")) or None,
        maglia_caricata=_testo(riga.get("maglia_caricata")) or None,
        anno_fondazione=None if anno is None or pd.isna(anno) else int(anno),
    )
    return Squadra(
        id=int(riga["id"]),
        nome=riga["nome"],
        presidente=identita.presidente,
        identita=identita,
    )


def carica_squadre(arch: Archivio) -> dict[int, Squadra]:
    return {
        int(riga["id"]): costruisci_squadra(riga) for _, riga in arch.squadre().iterrows()
    }


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
        squadra = costruisci_squadra(riga)

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


def salva_squadra(arch: Archivio, squadra: Squadra) -> None:
    """Persiste nome, presidente e identita' visiva di una squadra."""
    identita = squadra.identita
    arch.scrivi(
        "squadre",
        [
            {
                "id": squadra.id,
                "nome": squadra.nome,
                "presidente": identita.presidente,
                "motto": identita.motto,
                "stadio": identita.stadio,
                "colore_primario": identita.colore_primario,
                "colore_secondario": identita.colore_secondario,
                "stile_maglia": identita.stile_maglia.name,
                "logo": identita.logo,
                "maglia_caricata": identita.maglia_caricata,
                "anno_fondazione": identita.anno_fondazione,
            }
        ],
        chiave="id",
    )


def prossimo_id(arch: Archivio, tabella: str, colonna: str = "id") -> int:
    """Primo identificativo libero: serve per creare una squadra nuova."""
    esistenti = arch.tabella(tabella)
    if esistenti.empty or colonna not in esistenti.columns:
        return 1
    return int(esistenti[colonna].max()) + 1


def carica_credenziali(arch: Archivio) -> dict[str, Credenziali]:
    """Utenti indicizzati per nome utente, pronti per `autentica()`."""
    from .autenticazione import Credenziali, Ruolo, Utente

    righe = arch.tabella("utenti")
    if righe.empty:
        return {}

    credenziali: dict[str, Credenziali] = {}
    for _, r in righe.iterrows():
        try:
            ruolo = Ruolo(str(r["ruolo"]))
        except ValueError:
            ruolo = Ruolo.FANTALLENATORE
        squadra = r.get("squadra_id")
        utente = Utente(
            id=int(r["id"]),
            nome_utente=str(r["nome_utente"]).strip().lower(),
            nome=str(r["nome"]),
            ruolo=ruolo,
            squadra_id=None if squadra is None or pd.isna(squadra) else int(squadra),
            attivo=bool(r.get("attivo", True)),
        )
        credenziali[utente.nome_utente] = Credenziali(
            utente=utente,
            hash_password=str(r["hash_password"]),
            sale=str(r["sale"]),
        )
    return credenziali


def salva_credenziali(arch: Archivio, credenziali: Credenziali) -> None:
    utente = credenziali.utente
    arch.scrivi(
        "utenti",
        [
            {
                "id": utente.id,
                "nome_utente": utente.nome_utente,
                "nome": utente.nome,
                "hash_password": credenziali.hash_password,
                "sale": credenziali.sale,
                "ruolo": utente.ruolo.value,
                "squadra_id": utente.squadra_id,
                "attivo": int(utente.attivo),
            }
        ],
        chiave="id",
    )
