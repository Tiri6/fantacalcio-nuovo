"""Helper condivisi dalle pagine Streamlit: setup pagina e caricamenti in cache."""

from __future__ import annotations

import pandas as pd
import streamlit as st

from . import vista
from .config import carica_impostazioni
from .data import archivio, calendario_dettagliato, rose_dettagliate

TTL = 300  # secondi di cache: la lega cambia al massimo una volta a giornata


def configura_app() -> None:
    """set_page_config va chiamata una volta sola, dal router in app.py."""
    impostazioni = carica_impostazioni()
    st.set_page_config(
        page_title=impostazioni.nome_lega, page_icon="⚽", layout="wide"
    )


def intestazione(titolo: str, icona: str = "⚽") -> None:
    st.title(f"{icona} {titolo}")


def scheda(colonna, etichetta: str, valore: str, nota: str = "") -> None:
    """Come st.metric, ma il valore va a capo invece di essere troncato."""
    with colonna:
        st.caption(etichetta)
        st.markdown(f"#### {valore}")
        if nota:
            st.caption(nota)


def barra_laterale() -> None:
    """Mostra lega e backend attivo, con il pulsante per svuotare la cache."""
    impostazioni = carica_impostazioni()
    with st.sidebar:
        st.caption(impostazioni.nome_lega)
        if impostazioni.usa_supabase:
            st.success("Dati live da Supabase", icon="🟢")
        else:
            st.info(
                "Modalita' demo: dati generati in locale. "
                "Aggiungi SUPABASE_URL e SUPABASE_KEY nei secret per i dati veri.",
                icon="🧪",
            )
        if st.button("Ricarica dati", use_container_width=True):
            st.cache_data.clear()
            st.rerun()


@st.cache_data(ttl=TTL)
def squadre() -> pd.DataFrame:
    return archivio().squadre()


@st.cache_data(ttl=TTL)
def classifica() -> pd.DataFrame:
    return vista.classifica(archivio())


@st.cache_data(ttl=TTL)
def calendario() -> pd.DataFrame:
    return calendario_dettagliato(archivio())


@st.cache_data(ttl=TTL)
def rose() -> pd.DataFrame:
    return rose_dettagliate(archivio())


@st.cache_data(ttl=TTL)
def andamento_punti() -> pd.DataFrame:
    return vista.andamento_punti(archivio())


@st.cache_data(ttl=TTL)
def marcatori(quanti: int = 15) -> pd.DataFrame:
    return vista.classifica_marcatori(archivio(), quanti)


@st.cache_data(ttl=TTL)
def migliori_medie(presenze_minime: int = 3, quanti: int = 15) -> pd.DataFrame:
    return vista.migliori_per_media(archivio(), presenze_minime, quanti)


@st.cache_data(ttl=TTL)
def tabellino(squadra_id: int, giornata: int) -> pd.DataFrame:
    return vista.tabellino_squadra(archivio(), squadra_id, giornata)


def ultima_giornata_giocata(partite: pd.DataFrame) -> int:
    giocate = partite[partite["gol_casa"].notna()]
    return int(giocate["giornata"].max()) if not giocate.empty else 0


def formatta_partita(riga) -> str:
    """`Casa 2 - 1 Trasferta` per le partite giocate, `Casa - Trasferta` altrimenti."""
    if pd.isna(riga.gol_casa):
        return f"{riga.casa} — {riga.trasferta}"
    return (
        f"{riga.casa} {int(riga.gol_casa)} - "
        f"{int(riga.gol_trasferta)} {riga.trasferta}"
    )
