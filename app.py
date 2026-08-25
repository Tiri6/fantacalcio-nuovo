"""Punto di ingresso di FantaCalcio NuoVo: configura la pagina e la navigazione.

Prima del menu ci sono tre cancelli, in quest'ordine: accesso, lega, squadra.
Ognuno ferma la pagina finche' non e' superato, quindi da qui in giu' si puo'
dare per scontato che ci sia un utente dentro una lega.

Le singole schermate stanno in `viste/`. Si usa `st.navigation` invece della
cartella magica `pages/` per avere etichette e icone in italiano.
"""

import streamlit as st

from fantacalcio import ui

ui.configura_app()

utente = ui.richiedi_login()
lega = ui.richiedi_lega(utente)
ui.richiedi_squadra(utente, lega)

pagine = [
    # La bacheca e' la pagina d'ingresso: chi entra vuole sapere cosa e'
    # successo, non leggere una tabella di contratti.
    st.Page("viste/bacheca.py", title="Bacheca", icon="📣", default=True),
    st.Page("viste/home.py", title="Cruscotto", icon="🏠"),
    st.Page("viste/squadra.py", title="Rose e contratti", icon="📋"),
    st.Page("viste/mercato.py", title="Mercato", icon="🔁"),
    st.Page("viste/scambi.py", title="Scambi", icon="🤝"),
    st.Page("viste/identita.py", title="Identita' squadre", icon="🎨"),
    st.Page("viste/draft.py", title="Draft", icon="🎱"),
    st.Page("viste/calendario.py", title="Calendario", icon="📅"),
    st.Page("viste/campionato.py", title="Campionato", icon="🏆"),
    st.Page("viste/lega.py", title="La lega", icon="⚙️"),
    st.Page("viste/regolamento.py", title="Regolamento", icon="📖"),
]

# L'importazione riscrive intere rose: la vede solo il presidente (art. 1).
if utente.puo_importare:
    pagine.insert(6, st.Page("viste/importa.py", title="Importa dati", icon="📥"))

st.navigation(pagine).run()
