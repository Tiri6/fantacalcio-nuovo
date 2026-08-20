"""Calendario giornata per giornata, con il tabellino di ogni squadra."""

import pandas as pd
import streamlit as st

from fantacalcio import ui

ui.intestazione("Calendario e risultati", "📅")
ui.barra_laterale()

partite = ui.calendario()
squadre = ui.squadre()
if partite.empty:
    st.warning("Calendario non ancora generato.")
    st.stop()

ultima = ui.ultima_giornata_giocata(partite)
totale_giornate = int(partite["giornata"].max())

giornata = st.slider(
    "Giornata",
    min_value=1,
    max_value=totale_giornate,
    value=max(ultima, 1),
)

del_giorno = partite[partite["giornata"] == giornata]
id_per_nome = dict(zip(squadre["nome"], squadre["id"], strict=True))

for riga in del_giorno.itertuples():
    giocata = not pd.isna(riga.gol_casa)
    intestazione = ui.formatta_partita(riga)
    if giocata:
        intestazione += f"   ({riga.punti_casa:.1f} - {riga.punti_trasferta:.1f})"

    with st.expander(intestazione, expanded=False):
        if not giocata:
            st.caption("Partita non ancora giocata.")
            continue

        colonne = st.columns(2)
        for colonna, nome in zip(colonne, (riga.casa, riga.trasferta), strict=True):
            with colonna:
                st.markdown(f"**{nome}**")
                tabellino = ui.tabellino(id_per_nome[nome], giornata)
                if tabellino.empty:
                    st.caption("Formazione non registrata.")
                    continue
                st.caption(
                    f"Totale {tabellino.attrs['totale']:.1f} punti "
                    f"→ {tabellino.attrs['gol']} gol"
                )
                st.dataframe(tabellino, hide_index=True, use_container_width=True)
