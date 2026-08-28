"""Campionato: classifica, calendario e andamento. I risultati arrivano da Leghe."""

import pandas as pd
import plotly.express as px
import streamlit as st

from fantacalcio import ui

ui.intestazione(
    "Campionato",
    "🏆",
    "Risultati importati da Leghe Fantacalcio: qui servono per la classifica "
    "e per l'ordine del draft.",
)
ui.barra_laterale()

classifica = ui.classifica()
partite = ui.calendario()
if classifica.empty:
    st.warning("Ancora nessuna giornata disputata.")
    st.stop()

tabella, calendario, andamento = st.tabs(["Classifica", "Calendario", "Andamento"])

with tabella:
    st.dataframe(
        classifica,
        hide_index=True,
        use_container_width=True,
        column_config={"Punti fantacalcio": st.column_config.NumberColumn(format="%.1f")},
    )
    st.caption(
        "La classifica finale determina la Draft Lottery: le pick 1-5 si "
        "sorteggiano tra la seconda meta della classifica."
    )

with calendario:
    # Le squadre possono esistere senza che il calendario sia stato importato:
    # la classifica c'e' (tutte a zero) ma non c'e' nessuna partita.
    if partite.empty:
        st.info(
            "Il calendario non e' ancora stato importato. Si carica dalla "
            "pagina «Importa dati».",
            icon="🗓️",
        )
        totale = 0
    else:
        giornate = ui.giornate_disputate(partite)
        totale = int(partite["giornata"].max())
    if totale:
        giornata = st.slider("Giornata", 1, totale, max(giornate, 1))
        for riga in partite[partite["giornata"] == giornata].itertuples():
            st.write(ui.formatta_partita(riga))
            if not pd.isna(riga.punti_casa):
                st.caption(f"{riga.punti_casa:.1f} — {riga.punti_trasferta:.1f} punti")

with andamento:
    dati = ui.andamento_punti()
    if dati.empty:
        st.info("I grafici compaiono dopo la prima giornata.")
        st.stop()

    scelte = st.multiselect(
        "Squadre",
        options=sorted(dati["squadra"].unique()),
        placeholder="Scegli le squadre",
        default=classifica["Squadra"].head(4).tolist(),
    )
    if scelte:
        figura = px.line(
            dati[dati["squadra"].isin(scelte)],
            x="giornata",
            y="punti",
            color="squadra",
            markers=True,
            labels={"giornata": "Giornata", "punti": "Punti", "squadra": ""},
        )
        figura.update_layout(hovermode="x unified")
        st.plotly_chart(figura, use_container_width=True)

    st.subheader("Distribuzione dei punteggi")
    box = px.box(
        dati,
        x="squadra",
        y="punti",
        points="all",
        labels={"squadra": "", "punti": "Punti"},
    )
    box.update_layout(xaxis_tickangle=-30)
    st.plotly_chart(box, use_container_width=True)
