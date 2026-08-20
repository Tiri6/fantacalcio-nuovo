"""Draft: lottery, ordine di chiamata e probabilita' delle pick."""

import random

import pandas as pd
import plotly.express as px
import streamlit as st

from fantacalcio import ui, vista
from fantacalcio.draft import (
    PESI_FASCIA,
    distribuzione_pick,
    ordine_riparazione,
    sorteggia_lottery,
    tabellone_draft,
)

ui.intestazione("Draft", "🎱", "Draft Lottery e ordine di chiamata (art. 3).")
ui.barra_laterale()

classifica = ui.classifica()
if classifica.empty:
    st.warning("Serve una classifica per sorteggiare la Lottery.")
    st.stop()

ordine_classifica = classifica["Squadra"].tolist()

lottery, tabellone, riparazione = st.tabs(
    ["Draft Lottery", "Ordine di chiamata", "Asta di riparazione"]
)

with lottery:
    st.caption(
        "Due estrazioni distinte: le pick 1-5 tra la 10a e la 6a classificata, "
        f"le pick 6-10 tra la 5a e la 1a. Pesi per fascia: {PESI_FASCIA}."
    )

    seme = st.number_input(
        "Seme del sorteggio",
        min_value=0,
        value=2026,
        help="Stesso seme, stesso sorteggio: serve per rifare l'estrazione "
        "davanti a tutti.",
    )
    esito = sorteggia_lottery(ordine_classifica, random.Random(int(seme)))

    tabella = pd.DataFrame(
        {
            "Pick": range(1, len(esito.ordine) + 1),
            "Squadra": esito.ordine,
            "Posizione precedente": [
                ordine_classifica.index(s) + 1 for s in esito.ordine
            ],
        }
    )
    tabella["Fascia"] = [
        "1-5 (dalla 10a alla 6a)" if p <= 5 else "6-10 (dalla 5a alla 1a)"
        for p in tabella["Pick"]
    ]
    st.dataframe(tabella, hide_index=True, use_container_width=True)

    st.subheader("Probabilita' di ogni pick")
    st.caption(
        "I pesi valgono per la prima estrazione di ciascuna fascia; le pick "
        "successive dipendono da chi e' gia' uscito, quindi si stimano per "
        "simulazione."
    )
    distribuzione = distribuzione_pick(ordine_classifica, simulazioni=4000)
    matrice = pd.DataFrame(distribuzione).T.fillna(0.0)
    matrice = matrice.reindex(ordine_classifica)
    figura = px.imshow(
        matrice,
        labels={"x": "Pick", "y": "", "color": "Probabilita'"},
        text_auto=".0%",
        aspect="auto",
        color_continuous_scale="Greens",
    )
    figura.update_layout(margin={"t": 20, "b": 10, "l": 10, "r": 10})
    st.plotly_chart(figura, use_container_width=True)

with tabellone:
    st.caption(
        "Round 1 e 2 a serpente sull'ordine della Lottery. I round multipli di 3 "
        "si chiamano secondo l'ordine di arrivo della stagione precedente, dalla "
        "1a alla 10a. Tutti gli altri seguono la Lottery."
    )
    round_totali = st.slider("Round da mostrare", 3, 12, 6)
    esito_tabellone = sorteggia_lottery(ordine_classifica, random.Random(int(seme)))

    righe = []
    for numero, ordine in tabellone_draft(
        round_totali, esito_tabellone.ordine, ordine_classifica
    ):
        criterio = (
            "Classifica precedente"
            if numero % 3 == 0
            else ("Lottery invertita" if numero == 2 else "Lottery")
        )
        righe.append(
            {
                "Round": numero,
                "Criterio": criterio,
                **{f"{i}a": nome for i, nome in enumerate(ordine, start=1)},
            }
        )
    st.dataframe(pd.DataFrame(righe), hide_index=True, use_container_width=True)

with riparazione:
    st.caption(
        "Nell'asta di riparazione tutti i turni seguono l'ordine inverso di "
        "classifica al momento dell'apertura della finestra."
    )
    ordine = ordine_riparazione(ordine_classifica)
    st.dataframe(
        pd.DataFrame({"Turno": range(1, len(ordine) + 1), "Squadra": ordine}),
        hide_index=True,
        use_container_width=True,
    )

st.divider()
st.subheader("Draft list: contratti in scadenza")
st.caption("Chi arriva a scadenza naturale rientra nel draft della prossima asta.")
scadenze = vista.contratti_in_scadenza(ui.rose(), ui.DATA_DRAFT)
st.dataframe(
    ui.in_milioni(scadenze),
    hide_index=True,
    use_container_width=True,
    column_config=ui.COLONNE_EURO,
)
