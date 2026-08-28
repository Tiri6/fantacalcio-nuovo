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

from .bacheca import Annuncio, AnnuncioNonValido, TipoAnnuncio
from .competizioni import CompetizioneNonValida, TipoCompetizione, Titolo
from .config import Impostazioni, carica_impostazioni
from .demo_data import costruisci_db
from .identita import IdentitaSquadra, StileMaglia
from .leghe import (
    CodiceNonValido,
    EmailNonValida,
    Invito,
    Lega,
    LegaNonValida,
    OpzioniLega,
    StatoInvito,
)
from .modelli import Contratto, Giocatore, Rosa, Squadra, VoceDeadMoney

if TYPE_CHECKING:  # pragma: no cover - solo per i type checker
    from .autenticazione import Credenziali

TABELLE = (
    "leghe",
    "inviti",
    "annunci",
    "albo",
    "squadre",
    "giocatori",
    "contratti",
    "dead_money",
    "calendario",
    "utenti",
    "scambi",
    "scambi_movimenti",
)


# Le colonne che ogni tabella ha quando e' vuota.
#
# Serve perche' i due backend rispondono in modo diverso al «non c'e' niente»:
# SQLite restituisce una tabella vuota **con le sue colonne**, PostgREST
# restituisce una lista vuota, da cui pandas costruisce un DataFrame **senza
# colonne**. Il codice che poi fa `contratti["squadra_id"]` funziona sul primo
# e alza KeyError sul secondo — un guasto che in locale non si vede mai.
COLONNE_ATTESE: dict[str, tuple[str, ...]] = {
    "leghe": (
        "id",
        "nome",
        "codice_invito",
        "admin_id",
        "stagione",
        "opzioni",
        "creata_il",
    ),
    "inviti": ("id", "lega_id", "email", "codice", "stato", "creato_da", "creato_il"),
    "annunci": (
        "id",
        "lega_id",
        "titolo",
        "testo",
        "tipo",
        "autore_id",
        "autore_nome",
        "giornata",
        "pubblicato",
        "in_evidenza",
        "creato_il",
        "aggiornato_il",
    ),
    "albo": (
        "id",
        "lega_id",
        "competizione",
        "stagione",
        "squadra_id",
        "squadra_nome",
        "note",
        "registrato_il",
    ),
    "squadre": (
        "id",
        "nome",
        "presidente",
        "motto",
        "stadio",
        "citta",
        "curva",
        "colore_primario",
        "colore_secondario",
        "stile_maglia",
        "logo",
        "maglia_caricata",
        "anno_fondazione",
        "lega_id",
    ),
    "giocatori": (
        "id",
        "id_ufficiale",
        "nome",
        "club",
        "ruoli",
        "ingaggio",
        "nazionalita",
        "data_nascita",
        "quotazione",
        "fvm",
    ),
    "contratti": (
        "giocatore_id",
        "squadra_id",
        "anni_residui",
        "prolungato",
        "stagione_prolungamento",
    ),
    "dead_money": (
        "id",
        "squadra_id",
        "giocatore_id",
        "nome_giocatore",
        "importo",
        "stagione",
        "addebitato",
    ),
    "calendario": (
        "id",
        "giornata",
        "competizione",
        "giornata_serie_a",
        "data_prevista",
        "turno",
        "casa_id",
        "trasferta_id",
        "gol_casa",
        "gol_trasferta",
        "punti_casa",
        "punti_trasferta",
    ),
    "utenti": (
        "id",
        "nome_utente",
        "nome",
        "cognome",
        "hash_password",
        "sale",
        "ruolo",
        "email",
        "data_nascita",
        "sesso",
        "citta",
        "squadra_preferita",
        "squadra_id",
        "lega_id",
        "deve_cambiare_password",
        "attivo",
        "creato_il",
    ),
    "scambi": (
        "id",
        "squadra_a_id",
        "squadra_b_id",
        "proposto_da",
        "stato",
        "note",
        "creato_il",
        "aggiornato_il",
        "deciso_da",
        "ratificato_da",
        "giornata_efficacia",
    ),
    "scambi_movimenti": (
        "id",
        "scambio_id",
        "giocatore_id",
        "nome_giocatore",
        "da_squadra_id",
        "a_squadra_id",
        "anni_prima",
        "anni_dopo",
    ),
}


def con_colonne(nome: str, righe: pd.DataFrame) -> pd.DataFrame:
    """Garantisce che una tabella vuota abbia comunque le sue colonne.

    Cosi' chi legge puo' scrivere `contratti["squadra_id"]` senza chiedersi
    quale backend ha risposto.
    """
    if not righe.empty:
        return righe
    attese = COLONNE_ATTESE.get(nome)
    if not attese:
        return righe
    return pd.DataFrame(columns=list(attese))


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
            return con_colonne(nome, pd.read_sql_query(f"select * from {nome}", conn))

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
        # Senza righe PostgREST non dice quali colonne esistano: `con_colonne`
        # ci mette quelle attese, cosi' chi legge non deve saperlo.
        return con_colonne(nome, pd.DataFrame(risposta.data or []))

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
        citta=_testo(riga.get("citta")),
        curva=_testo(riga.get("curva")),
        colore_primario=_testo(riga.get("colore_primario"), "#2e7d32"),
        colore_secondario=_testo(riga.get("colore_secondario"), "#ffffff"),
        stile_maglia=stile_maglia,
        logo=_testo(riga.get("logo")) or None,
        maglia_caricata=_testo(riga.get("maglia_caricata")) or None,
        anno_fondazione=None if anno is None or pd.isna(anno) else int(anno),
    )
    lega = riga.get("lega_id")
    return Squadra(
        id=int(riga["id"]),
        nome=riga["nome"],
        presidente=identita.presidente,
        identita=identita,
        lega_id=None if lega is None or pd.isna(lega) else int(lega),
    )


def carica_squadre(arch: Archivio) -> dict[int, Squadra]:
    return {
        int(riga["id"]): costruisci_squadra(riga) for _, riga in arch.squadre().iterrows()
    }


def _numero(valore) -> float | None:
    if valore is None or pd.isna(valore):
        return None
    return float(valore)


def carica_giocatori(arch: Archivio) -> dict[int, Giocatore]:
    """Anagrafica di tutti i giocatori della lega, indicizzata per id."""
    ufficiale = None
    return {
        int(riga["id"]): Giocatore(
            id=int(riga["id"]),
            nome=riga["nome"],
            club=riga["club"],
            ruoli=tuple(str(riga["ruoli"]).split(";")),
            ingaggio=float(riga["ingaggio"]),
            nazionalita=riga["nazionalita"],
            data_nascita=_data(riga.get("data_nascita")),
            id_ufficiale=(
                None
                if (ufficiale := riga.get("id_ufficiale")) is None or pd.isna(ufficiale)
                else int(ufficiale)
            ),
            quotazione=_numero(riga.get("quotazione")),
            fvm=_numero(riga.get("fvm")),
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
                "citta": identita.citta,
                "curva": identita.curva,
                "colore_primario": identita.colore_primario,
                "colore_secondario": identita.colore_secondario,
                "stile_maglia": identita.stile_maglia.name,
                "logo": identita.logo,
                "maglia_caricata": identita.maglia_caricata,
                "anno_fondazione": identita.anno_fondazione,
                "lega_id": squadra.lega_id,
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


def _sesso(valore):
    """Il nome del membro di Sesso. Un valore ignoto non deve far fallire tutto."""
    from .anagrafica import Sesso

    try:
        return Sesso[_testo(valore, "NON_DICHIARATO")]
    except KeyError:
        return Sesso.NON_DICHIARATO


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
        lega = r.get("lega_id")
        utente = Utente(
            id=int(r["id"]),
            nome_utente=str(r["nome_utente"]).strip().lower(),
            nome=str(r["nome"]),
            ruolo=ruolo,
            squadra_id=None if squadra is None or pd.isna(squadra) else int(squadra),
            lega_id=None if lega is None or pd.isna(lega) else int(lega),
            email=_testo(r.get("email")) or None,
            attivo=bool(r.get("attivo", True)),
            deve_cambiare_password=bool(r.get("deve_cambiare_password", False)),
            cognome=_testo(r.get("cognome")),
            data_nascita=_data(r.get("data_nascita")),
            sesso=_sesso(r.get("sesso")),
            citta=_testo(r.get("citta")),
            squadra_preferita=_testo(r.get("squadra_preferita")),
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
                "email": utente.email,
                "cognome": utente.cognome,
                "data_nascita": (
                    utente.data_nascita.isoformat() if utente.data_nascita else None
                ),
                "sesso": utente.sesso.name,
                "citta": utente.citta,
                "squadra_preferita": utente.squadra_preferita,
                "squadra_id": utente.squadra_id,
                "lega_id": utente.lega_id,
                "deve_cambiare_password": int(utente.deve_cambiare_password),
                "attivo": int(utente.attivo),
            }
        ],
        chiave="id",
    )


# ---------------------------------------------------------------------------
# Leghe e inviti
# ---------------------------------------------------------------------------


def carica_leghe(arch: Archivio) -> dict[int, Lega]:
    """Tutte le leghe, indicizzate per id. Le righe illeggibili si saltano.

    Saltare invece di esplodere e' voluto: una lega scritta male non deve
    impedire a chi gioca nelle altre di entrare.
    """
    righe = arch.tabella("leghe")
    if righe.empty:
        return {}

    leghe: dict[int, Lega] = {}
    for _, r in righe.iterrows():
        admin = r.get("admin_id")
        try:
            lega = Lega(
                id=int(r["id"]),
                nome=str(r["nome"]),
                codice_invito=str(r["codice_invito"]),
                admin_id=0 if admin is None or pd.isna(admin) else int(admin),
                stagione=_testo(r.get("stagione"), "2026/27"),
                opzioni=OpzioniLega.da_json(_testo(r.get("opzioni")) or None),
                creata_il=_testo(r.get("creata_il")),
            )
        except (LegaNonValida, CodiceNonValido, KeyError, TypeError, ValueError):
            continue
        leghe[lega.id] = lega
    return leghe


def salva_lega(arch: Archivio, lega: Lega) -> None:
    arch.scrivi(
        "leghe",
        [
            {
                "id": lega.id,
                "nome": lega.nome,
                "codice_invito": lega.codice_invito,
                "admin_id": lega.admin_id,
                "stagione": lega.stagione,
                "opzioni": lega.opzioni.a_json(),
                "creata_il": lega.creata_il,
            }
        ],
        chiave="id",
    )


def carica_inviti(arch: Archivio, lega_id: int | None = None) -> list[Invito]:
    """Inviti registrati, eventualmente filtrati su una lega sola."""
    righe = arch.tabella("inviti")
    if righe.empty:
        return []

    inviti: list[Invito] = []
    for _, r in righe.iterrows():
        if lega_id is not None and int(r["lega_id"]) != lega_id:
            continue
        try:
            stato = StatoInvito(str(r.get("stato", "in_attesa")))
        except ValueError:
            stato = StatoInvito.IN_ATTESA
        creato_da = r.get("creato_da")
        try:
            inviti.append(
                Invito(
                    id=int(r["id"]),
                    lega_id=int(r["lega_id"]),
                    email=str(r["email"]),
                    codice=str(r["codice"]),
                    stato=stato,
                    creato_da=(
                        None
                        if creato_da is None or pd.isna(creato_da)
                        else int(creato_da)
                    ),
                    creato_il=_testo(r.get("creato_il")),
                )
            )
        except (EmailNonValida, CodiceNonValido, KeyError, TypeError, ValueError):
            continue
    return inviti


def salva_invito(arch: Archivio, invito: Invito) -> None:
    arch.scrivi(
        "inviti",
        [
            {
                "id": invito.id,
                "lega_id": invito.lega_id,
                "email": invito.email,
                "codice": invito.codice,
                "stato": invito.stato.value,
                "creato_da": invito.creato_da,
                "creato_il": invito.creato_il,
            }
        ],
        chiave="id",
    )


# ---------------------------------------------------------------------------
# Bacheca
# ---------------------------------------------------------------------------


def carica_annunci(arch: Archivio, lega_id: int | None = None) -> list[Annuncio]:
    """Annunci della bacheca. Le righe illeggibili si saltano, non esplodono."""
    righe = arch.tabella("annunci")
    if righe.empty:
        return []

    annunci: list[Annuncio] = []
    for _, r in righe.iterrows():
        if lega_id is not None and int(r["lega_id"]) != lega_id:
            continue
        try:
            tipo = TipoAnnuncio[str(r.get("tipo", "NOTIZIA"))]
        except KeyError:
            tipo = TipoAnnuncio.NOTIZIA
        giornata = r.get("giornata")
        autore = r.get("autore_id")
        try:
            annunci.append(
                Annuncio(
                    id=int(r["id"]),
                    lega_id=int(r["lega_id"]),
                    titolo=str(r["titolo"]),
                    testo=str(r["testo"]),
                    tipo=tipo,
                    autore_id=(0 if autore is None or pd.isna(autore) else int(autore)),
                    autore_nome=_testo(r.get("autore_nome")),
                    giornata=(
                        None if giornata is None or pd.isna(giornata) else int(giornata)
                    ),
                    pubblicato=bool(r.get("pubblicato", True)),
                    in_evidenza=bool(r.get("in_evidenza", False)),
                    creato_il=_testo(r.get("creato_il")),
                    aggiornato_il=_testo(r.get("aggiornato_il")),
                )
            )
        except (AnnuncioNonValido, KeyError, TypeError, ValueError):
            continue
    return annunci


def salva_annuncio(arch: Archivio, annuncio: Annuncio) -> None:
    arch.scrivi(
        "annunci",
        [
            {
                "id": annuncio.id,
                "lega_id": annuncio.lega_id,
                "titolo": annuncio.titolo,
                "testo": annuncio.testo,
                "tipo": annuncio.tipo.name,
                "autore_id": annuncio.autore_id,
                "autore_nome": annuncio.autore_nome,
                "giornata": annuncio.giornata,
                "pubblicato": int(annuncio.pubblicato),
                "in_evidenza": int(annuncio.in_evidenza),
                "creato_il": annuncio.creato_il,
                "aggiornato_il": annuncio.aggiornato_il,
            }
        ],
        chiave="id",
    )


def elimina_annuncio(arch: Archivio, annuncio_id: int) -> None:
    """Cancella un annuncio. Il backend demo e Supabase cancellano diversamente."""
    if isinstance(arch, ArchivioSQLite):
        with sqlite3.connect(arch.percorso) as conn:
            conn.execute("delete from annunci where id = ?", (annuncio_id,))
        return
    arch._client.table("annunci").delete().eq("id", annuncio_id).execute()


# ---------------------------------------------------------------------------
# Albo d'oro
# ---------------------------------------------------------------------------


def carica_albo(arch: Archivio, lega_id: int | None = None) -> list[Titolo]:
    """I titoli vinti. Le righe illeggibili si saltano invece di far fallire."""
    righe = arch.tabella("albo")
    if righe.empty:
        return []

    titoli: list[Titolo] = []
    for _, r in righe.iterrows():
        if lega_id is not None and int(r["lega_id"]) != lega_id:
            continue
        try:
            competizione = TipoCompetizione[str(r["competizione"])]
        except KeyError:
            continue
        squadra = r.get("squadra_id")
        try:
            titoli.append(
                Titolo(
                    id=int(r["id"]),
                    lega_id=int(r["lega_id"]),
                    competizione=competizione,
                    stagione=str(r["stagione"]),
                    squadra_id=(
                        None if squadra is None or pd.isna(squadra) else int(squadra)
                    ),
                    squadra_nome=str(r["squadra_nome"]),
                    note=_testo(r.get("note")),
                    registrato_il=_testo(r.get("registrato_il")),
                )
            )
        except (CompetizioneNonValida, KeyError, TypeError, ValueError):
            continue
    return titoli


def salva_titolo(arch: Archivio, titolo: Titolo) -> None:
    arch.scrivi(
        "albo",
        [
            {
                "id": titolo.id,
                "lega_id": titolo.lega_id,
                "competizione": titolo.competizione.name,
                "stagione": titolo.stagione,
                "squadra_id": titolo.squadra_id,
                "squadra_nome": titolo.squadra_nome,
                "note": titolo.note,
                "registrato_il": titolo.registrato_il,
            }
        ],
        chiave="id",
    )


def elimina_titolo(arch: Archivio, titolo_id: int) -> None:
    if isinstance(arch, ArchivioSQLite):
        with sqlite3.connect(arch.percorso) as conn:
            conn.execute("delete from albo where id = ?", (titolo_id,))
        return
    arch._client.table("albo").delete().eq("id", titolo_id).execute()
