"""Home della lega: colpo d'occhio su classifica, ultima e prossima giornata."""

import pandas as pd
import streamlit as st

from fantacalcio import ui

ui.intestazione("Casa della Lega", "⚽")
ui.barra_laterale()

classifica = ui.classifica()
partite = ui.calendario()

if classifica.empty:
    st.error("Nessun dato disponibile: controlla la connessione al database.")
    st.stop()

ultima = ui.ultima_giornata_giocata(partite)
capolista = classifica.iloc[0]
miglior_attacco = classifica.loc[classifica["GF"].idxmax()]

colonne = st.columns(4)
colonne[0].metric("Squadre", len(classifica))
colonne[1].metric("Giornate giocate", ultima)
ui.scheda(colonne[2], "Capolista", capolista["Squadra"], f"{capolista['Punti']} punti")
ui.scheda(
    colonne[3],
    "Miglior attacco",
    miglior_attacco["Squadra"],
    f"{int(miglior_attacco['GF'])} gol fatti",
)

st.divider()
sinistra, destra = st.columns([3, 2])

with sinistra:
    st.subheader("Classifica")
    st.dataframe(
        classifica[["Pos", "Squadra", "PG", "Punti", "DR", "Punti fantacalcio"]],
        hide_index=True,
        use_container_width=True,
        column_config={
            "Punti fantacalcio": st.column_config.NumberColumn(format="%.1f")
        },
    )

with destra:
    if ultima:
        st.subheader(f"Risultati {ultima}ª giornata")
        for riga in partite[partite["giornata"] == ultima].itertuples():
            st.write(ui.formatta_partita(riga))
            if not pd.isna(riga.punti_casa):
                st.caption(f"{riga.punti_casa:.1f} — {riga.punti_trasferta:.1f} punti")

    prossima = partite[partite["giornata"] == ultima + 1]
    if not prossima.empty:
        st.subheader(f"Prossima giornata ({ultima + 1}ª)")
        for riga in prossima.itertuples():
            st.write(f"{riga.casa} — {riga.trasferta}")

st.divider()
st.caption("Usa il menu a sinistra per classifica, calendario, rose e statistiche.")
