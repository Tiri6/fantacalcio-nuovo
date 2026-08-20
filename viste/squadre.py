"""Rose delle squadre della lega e rendimento dei singoli giocatori."""

import plotly.express as px
import streamlit as st

from fantacalcio import ui
from fantacalcio.vista import ETICHETTE_RUOLO

ui.intestazione("Squadre e rose", "👥")
ui.barra_laterale()

rose = ui.rose()
classifica = ui.classifica()
if rose.empty:
    st.warning("Nessuna rosa registrata.")
    st.stop()

nomi = sorted(rose["squadra"].unique())
scelta = st.selectbox("Squadra", nomi)

rosa = rose[rose["squadra"] == scelta].copy()
rosa["Ruolo"] = rosa["ruolo"].map(ETICHETTE_RUOLO)

riga_classifica = classifica[classifica["Squadra"] == scelta]
if not riga_classifica.empty:
    dati = riga_classifica.iloc[0]
    colonne = st.columns(4)
    colonne[0].metric("Posizione", f"{int(dati['Pos'])}º")
    colonne[1].metric("Punti", int(dati["Punti"]))
    colonne[2].metric("Gol fatti / subiti", f"{int(dati['GF'])} / {int(dati['GS'])}")
    colonne[3].metric("Media punti", f"{dati['Media punti']:.2f}")

st.caption(f"Allenatore: {rosa['allenatore'].iloc[0]}")

sinistra, destra = st.columns([3, 2])

with sinistra:
    st.subheader("Rosa")
    st.dataframe(
        rosa[["giocatore", "Ruolo", "club", "quotazione", "prezzo"]].rename(
            columns={
                "giocatore": "Giocatore",
                "club": "Club",
                "quotazione": "Quotazione",
                "prezzo": "Pagato",
            }
        ),
        hide_index=True,
        use_container_width=True,
    )

with destra:
    st.subheader("Spesa per ruolo")
    per_ruolo = rosa.groupby("Ruolo", as_index=False)["prezzo"].sum()
    figura = px.pie(per_ruolo, names="Ruolo", values="prezzo", hole=0.45)
    figura.update_traces(textposition="inside", textinfo="percent+label")
    figura.update_layout(
        showlegend=False, margin={"t": 10, "b": 10, "l": 10, "r": 10}
    )
    st.plotly_chart(figura, use_container_width=True)
    st.metric("Crediti spesi", int(rosa["prezzo"].sum()))
