"""Helper condivisi dalle pagine Streamlit: setup, cache e formattazioni."""

from __future__ import annotations

import base64
from datetime import date

import pandas as pd
import streamlit as st

from . import vista
from .config import carica_impostazioni
from .conformita import Momento
from .data import archivio, calendario_dettagliato, carica_rose
from .regole import CalendarioStagione, ParametriLega

TTL = 300  # secondi: la lega cambia al massimo una volta a giornata

DATA_DRAFT = date(2026, 9, 15)
CALENDARIO = CalendarioStagione(data_draft_settembre=DATA_DRAFT)


def parametri() -> ParametriLega:
    return ParametriLega()


def configura_app() -> None:
    """set_page_config va chiamata una volta sola, dal router in app.py."""
    st.set_page_config(
        page_title=carica_impostazioni().nome_lega, page_icon="⚽", layout="wide"
    )


def intestazione(titolo: str, icona: str = "⚽", sottotitolo: str = "") -> None:
    st.title(f"{icona} {titolo}")
    if sottotitolo:
        st.caption(sottotitolo)


def barra_laterale() -> None:
    """Lega, backend attivo e pulsante per svuotare la cache."""
    impostazioni = carica_impostazioni()
    with st.sidebar:
        st.caption(impostazioni.nome_lega)
        if impostazioni.usa_supabase:
            st.success("Dati live da Supabase", icon="🟢")
        else:
            st.info(
                "Modalita' demo: lega generata in locale. Aggiungi SUPABASE_URL e "
                "SUPABASE_KEY nei secret per i dati veri.",
                icon="🧪",
            )
        if st.button("Ricarica dati", use_container_width=True):
            invalida_dati()
            st.rerun()


def milioni(importo: float) -> str:
    return f"{importo / 1_000_000:.2f}M"


COLONNE_EURO = {
    nome: st.column_config.NumberColumn(format="%.2f M")
    for nome in (
        "Ingaggi",
        "Dead money",
        "Spesa",
        "Spazio cap",
        "Ingaggio",
        "Valore residuo",
        "Dead money se tagliato",
    )
}


def in_milioni(tabella: pd.DataFrame) -> pd.DataFrame:
    """Riscala le colonne in euro a milioni, per leggerle senza contare gli zeri."""
    copia = tabella.copy()
    for colonna in COLONNE_EURO:
        if colonna in copia.columns:
            copia[colonna] = copia[colonna] / 1_000_000
    return copia


# --- caricamenti in cache ---------------------------------------------------
#
# Le cache sono indicizzate su un numero di versione invece di essere svuotate
# con `cache_data.clear()`: svuotare una cache provoca un rerun immediato, che
# cancellerebbe il messaggio di conferma appena mostrato dopo un salvataggio.

CHIAVE_VERSIONE = "_versione_dati"


def versione_dati() -> int:
    return st.session_state.get(CHIAVE_VERSIONE, 0)


def invalida_dati() -> None:
    """Da chiamare dopo ogni scrittura: le viste ricaricheranno da sole."""
    st.session_state[CHIAVE_VERSIONE] = versione_dati() + 1


@st.cache_data(ttl=TTL)
def _squadre(versione: int) -> pd.DataFrame:
    return archivio().squadre()


def squadre() -> pd.DataFrame:
    return _squadre(versione_dati())


@st.cache_resource(ttl=TTL)
def _rose(versione: int):
    """Le rose sono oggetti di dominio, non dati serializzabili: cache_resource."""
    return carica_rose(archivio())


def rose():
    return _rose(versione_dati())


@st.cache_data(ttl=TTL)
def _classifica(versione: int) -> pd.DataFrame:
    return vista.classifica(archivio())


def classifica() -> pd.DataFrame:
    return _classifica(versione_dati())


@st.cache_data(ttl=TTL)
def _calendario(versione: int) -> pd.DataFrame:
    return calendario_dettagliato(archivio())


def calendario() -> pd.DataFrame:
    return _calendario(versione_dati())


@st.cache_data(ttl=TTL)
def _andamento_punti(versione: int) -> pd.DataFrame:
    return vista.andamento_punti(archivio())


def andamento_punti() -> pd.DataFrame:
    return _andamento_punti(versione_dati())


def stati(momento: Momento = Momento.STAGIONE):
    return vista.stati_rose(rose(), DATA_DRAFT, parametri(), momento)


def giornate_disputate(partite: pd.DataFrame) -> int:
    giocate = partite[partite["gol_casa"].notna()]
    return int(giocate["giornata"].max()) if not giocate.empty else 0


def formatta_partita(riga) -> str:
    if pd.isna(riga.gol_casa):
        return f"{riga.casa} — {riga.trasferta}"
    return (
        f"{riga.casa} {int(riga.gol_casa)} - {int(riga.gol_trasferta)} {riga.trasferta}"
    )


def badge_esito(conforme: bool) -> str:
    return "🟢 Conforme" if conforme else "🔴 Da sistemare"


def mostra_violazioni(violazioni) -> None:
    """Elenca le violazioni distinguendo blocchi e avvisi."""
    if not violazioni:
        st.success("Nessuna violazione: rosa conforme al regolamento.", icon="✅")
        return
    for v in violazioni:
        testo = f"**{v.articolo}** — {v.messaggio}"
        if v.bloccante:
            st.error(testo, icon="⛔")
        else:
            st.warning(testo, icon="⚠️")


def mostra_maglia(squadra_o_identita, larghezza: int = 160, didascalia: str = "") -> None:
    """Disegna la maglia. Se e' stata caricata un'immagine, mostra quella.

    Si passa sempre da un data URI: `st.html` non renderizza l'SVG inline, e
    cosi' maglia disegnata e maglia caricata seguono la stessa strada.
    """
    identita = getattr(squadra_o_identita, "identita", squadra_o_identita)
    contenuto = identita.maglia(larghezza)

    if not contenuto.startswith("data:"):
        codificato = base64.b64encode(contenuto.encode("utf-8")).decode("ascii")
        contenuto = f"data:image/svg+xml;base64,{codificato}"

    st.image(contenuto, width=larghezza, caption=didascalia or None)


def mostra_logo(identita, larghezza: int = 96) -> None:
    if identita.logo:
        st.image(identita.logo, width=larghezza)


def pastiglia_colore(colore: str, etichetta: str = "") -> str:
    """Quadratino colorato da mettere in linea con il testo."""
    return (
        f'<span style="display:inline-block;width:14px;height:14px;'
        f"border-radius:3px;background:{colore};border:1px solid #8884;"
        f'vertical-align:-2px;margin-right:6px"></span>{etichetta}'
    )
