"""Classifica completa con l'andamento della posizione giornata per giornata."""

import plotly.express as px
import streamlit as st

from fantacalcio import ui

ui.intestazione("Classifica", "🏆")
ui.barra_laterale()

classifica = ui.classifica()
if classifica.empty:
    st.warning("Ancora nessuna giornata giocata.")
    st.stop()

st.dataframe(
    classifica,
    hide_index=True,
    use_container_width=True,
    column_config={
        "Punti fantacalcio": st.column_config.NumberColumn(format="%.2f"),
        "Media punti": st.column_config.NumberColumn(format="%.2f"),
    },
)

st.subheader("Punti fantacalcio per giornata")
andamento = ui.andamento_punti()
if andamento.empty:
    st.info("I grafici compaiono dopo la prima giornata giocata.")
    st.stop()

squadre_scelte = st.multiselect(
    "Squadre da confrontare",
    options=sorted(andamento["squadra"].unique()),
    default=classifica["Squadra"].head(4).tolist(),
)
if squadre_scelte:
    filtrato = andamento[andamento["squadra"].isin(squadre_scelte)]
    figura = px.line(
        filtrato,
        x="giornata",
        y="punti",
        color="squadra",
        markers=True,
        labels={"giornata": "Giornata", "punti": "Punti", "squadra": "Squadra"},
    )
    figura.update_layout(hovermode="x unified", legend_title_text="")
    st.plotly_chart(figura, use_container_width=True)

st.subheader("Punti totali accumulati")
cumulato = andamento.copy()
cumulato["totale"] = cumulato.groupby("squadra")["punti"].cumsum()
figura_totale = px.line(
    cumulato,
    x="giornata",
    y="totale",
    color="squadra",
    labels={"giornata": "Giornata", "totale": "Punti totali", "squadra": "Squadra"},
)
figura_totale.update_layout(legend_title_text="")
st.plotly_chart(figura_totale, use_container_width=True)
