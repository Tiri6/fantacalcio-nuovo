"""Configurazione dell'app: quale backend dati usare e con quali credenziali.

In sessioni cloud (Claude Code sul web, CI) i secret non ci sono: l'app cade
automaticamente sul database SQLite di demo, cosi' e' sempre avviabile.
"""

from __future__ import annotations

import os
from dataclasses import dataclass
from pathlib import Path

RADICE = Path(__file__).resolve().parents[1]
DB_DEMO = RADICE / "data" / "fantacalcio_nuovo.db"


def _da_streamlit(chiave: str) -> str | None:
    """Legge un secret di Streamlit senza esplodere se il file non esiste."""
    try:
        import streamlit as st

        return st.secrets.get(chiave)  # type: ignore[no-any-return]
    except Exception:  # noqa: BLE001 - senza secrets.toml Streamlit alza tipi diversi
        # a seconda della versione (FileNotFoundError, StreamlitSecretNotFoundError):
        # qualunque errore qui significa solo "nessun secret disponibile".
        return None


def leggi_secret(chiave: str) -> str | None:
    """Prima le variabili d'ambiente, poi i secret di Streamlit."""
    valore = os.environ.get(chiave)
    if valore:
        return valore.strip()
    valore = _da_streamlit(chiave)
    return valore.strip() if isinstance(valore, str) and valore.strip() else None


@dataclass(frozen=True)
class Impostazioni:
    supabase_url: str | None
    supabase_key: str | None
    percorso_db_demo: Path
    nome_lega: str

    @property
    def usa_supabase(self) -> bool:
        return bool(self.supabase_url and self.supabase_key)

    @property
    def backend(self) -> str:
        return "supabase" if self.usa_supabase else "demo (SQLite)"


def carica_impostazioni() -> Impostazioni:
    return Impostazioni(
        supabase_url=leggi_secret("SUPABASE_URL"),
        supabase_key=leggi_secret("SUPABASE_KEY"),
        percorso_db_demo=Path(leggi_secret("FANTA_DB_DEMO") or DB_DEMO),
        nome_lega=leggi_secret("NOME_LEGA") or "FantaCalcio NuoVo",
    )
