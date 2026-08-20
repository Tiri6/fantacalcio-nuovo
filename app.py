"""Punto di ingresso del sito: configura la pagina e monta la navigazione.

Le singole schermate stanno in `viste/`. Si usa `st.navigation` invece della
cartella magica `pages/` per avere etichette e icone in italiano.
"""

import streamlit as st

from fantacalcio import ui

ui.configura_app()

navigazione = st.navigation(
    [
        st.Page("viste/home.py", title="Home", icon="🏠", default=True),
        st.Page("viste/classifica.py", title="Classifica", icon="🏆"),
        st.Page("viste/calendario.py", title="Calendario", icon="📅"),
        st.Page("viste/squadre.py", title="Squadre e rose", icon="👥"),
        st.Page("viste/statistiche.py", title="Statistiche", icon="📊"),
    ]
)
navigazione.run()
