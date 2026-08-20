"""Punto di ingresso di FantaCalcio NuoVo: configura la pagina e la navigazione.

Le singole schermate stanno in `viste/`. Si usa `st.navigation` invece della
cartella magica `pages/` per avere etichette e icone in italiano.
"""

import streamlit as st

from fantacalcio import ui

ui.configura_app()

navigazione = st.navigation(
    [
        st.Page("viste/home.py", title="Cruscotto", icon="🏠", default=True),
        st.Page("viste/squadra.py", title="Rose e contratti", icon="📋"),
        st.Page("viste/mercato.py", title="Mercato", icon="🔁"),
        st.Page("viste/identita.py", title="Identita' squadre", icon="🎨"),
        st.Page("viste/importa.py", title="Importa dati", icon="📥"),
        st.Page("viste/draft.py", title="Draft", icon="🎱"),
        st.Page("viste/campionato.py", title="Campionato", icon="🏆"),
        st.Page("viste/regolamento.py", title="Regolamento", icon="📖"),
    ]
)
navigazione.run()
