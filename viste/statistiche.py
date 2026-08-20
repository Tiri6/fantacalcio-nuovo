"""Statistiche della lega: marcatori, medie e distribuzione dei punteggi."""

import plotly.express as px
import streamlit as st

from fantacalcio import ui
from fantacalcio.vista import ETICHETTE_RUOLO

ui.intestazione("Statistiche", "📊")
ui.barra_laterale()

andamento = ui.andamento_punti()
if andamento.empty:
    st.warning("Le statistiche compaiono dopo la prima giornata giocata.")
    st.stop()

marcatori, medie, punteggi = st.tabs(
    ["Marcatori", "Migliori medie", "Punteggi di squadra"]
)

with marcatori:
    quanti = st.slider("Quanti giocatori", 5, 30, 15, key="quanti_marcatori")
    tabella = ui.marcatori(quanti).rename(
        columns={
            "giocatore": "Giocatore",
            "ruolo": "Ruolo",
            "club": "Club",
            "squadra": "Fantasquadra",
            "gol": "Gol",
            "assist": "Assist",
            "presenze": "Presenze",
            "media_voto": "Media voto",
        }
    )
    tabella["Ruolo"] = tabella["Ruolo"].map(ETICHETTE_RUOLO)
    st.dataframe(tabella, hide_index=True, use_container_width=True)

with medie:
    presenze_minime = st.slider("Presenze minime", 1, 10, 3)
    tabella = ui.migliori_medie(presenze_minime, 20).rename(
        columns={
            "giocatore": "Giocatore",
            "ruolo": "Ruolo",
            "club": "Club",
            "squadra": "Fantasquadra",
            "presenze": "Presenze",
            "media_fantavoto": "Media fantavoto",
            "media_voto": "Media voto",
        }
    )
    tabella["Ruolo"] = tabella["Ruolo"].map(ETICHETTE_RUOLO)
    st.dataframe(
        tabella,
        hide_index=True,
        use_container_width=True,
        column_config={
            "Media fantavoto": st.column_config.NumberColumn(format="%.2f"),
            "Media voto": st.column_config.NumberColumn(format="%.2f"),
        },
    )

with punteggi:
    st.subheader("Distribuzione dei punteggi di squadra")
    figura = px.box(
        andamento,
        x="squadra",
        y="punti",
        points="all",
        labels={"squadra": "", "punti": "Punti fantacalcio"},
    )
    figura.update_layout(xaxis_tickangle=-30)
    st.plotly_chart(figura, use_container_width=True)

    colonne = st.columns(3)
    migliore = andamento.loc[andamento["punti"].idxmax()]
    peggiore = andamento.loc[andamento["punti"].idxmin()]
    colonne[0].metric(
        "Miglior punteggio",
        f"{migliore['punti']:.1f}",
        f"{migliore['squadra']} · {int(migliore['giornata'])}ª",
    )
    colonne[1].metric(
        "Peggior punteggio",
        f"{peggiore['punti']:.1f}",
        f"{peggiore['squadra']} · {int(peggiore['giornata'])}ª",
    )
    colonne[2].metric("Media della lega", f"{andamento['punti'].mean():.1f}")
