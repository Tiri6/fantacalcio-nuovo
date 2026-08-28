"""Identita' delle squadre: presidente, motto, stadio, colori, maglia e logo."""

import streamlit as st

from fantacalcio import schermate, ui

NUOVA = "➕ Crea una squadra nuova"

ui.intestazione(
    "Identita' delle squadre",
    "🎨",
    "Presidente, motto, stadio, citta', curva, colori sociali, maglia e logo.",
)
ui.barra_laterale()

schermate.mostra_messaggio()

rose = ui.rose()
squadre = {rosa.squadra.nome: rosa.squadra for rosa in rose.values()}

galleria, scheda = st.tabs(["Galleria della lega", "Crea o modifica"])

with galleria:
    st.caption("Le maglie sono disegnate dai colori sociali di ogni squadra.")
    nomi = sorted(squadre)
    for inizio in range(0, len(nomi), 5):
        colonne = st.columns(5)
        for colonna, nome in zip(colonne, nomi[inizio : inizio + 5], strict=False):
            squadra = squadre[nome]
            with colonna:
                ui.mostra_maglia(squadra, larghezza=130)
                st.markdown(f"**{nome}**")
                if squadra.presidente:
                    st.caption(f"Presidente: {squadra.presidente}")
                if squadra.motto:
                    st.caption(f"_{squadra.motto}_")
                if squadra.stadio:
                    casa = squadra.stadio
                    if squadra.citta:
                        casa += f", {squadra.citta}"
                    st.caption(f"🏟️ {casa}")
                elif squadra.citta:
                    st.caption(f"📍 {squadra.citta}")
                if squadra.curva:
                    st.caption(f"📣 {squadra.curva}")

with scheda:
    utente = ui.utente_corrente()
    lega = ui.lega_corrente()

    # Il presidente vede tutte le squadre; gli altri solo la propria. Il
    # controllo sta qui **e** in `Utente.puo_gestire`: prima non c'era, e
    # chiunque poteva riscrivere l'identita' di chiunque.
    modificabili = sorted(
        nome for nome, sq in squadre.items() if utente.puo_gestire(sq.id)
    )
    scelte = ([NUOVA] if utente.puo_importare else []) + modificabili

    if not scelte:
        st.info(
            "Non hai ancora una squadra da modificare. La fondi dalla schermata "
            "d'ingresso, oppure te la crea il presidente di lega.",
            icon="🛡️",
        )
        st.stop()

    scelta = st.selectbox("Squadra", scelte)
    nuova = scelta == NUOVA
    squadra = None if nuova else squadre[scelta]

    if not utente.puo_importare:
        st.caption("Puoi modificare la tua squadra. Le altre le vedi nella galleria.")

    schermate.modulo_identita(
        squadra,
        lega,
        nomi_occupati={n.lower() for n in squadre if nuova or n != scelta},
        chiave="identita",
    )
