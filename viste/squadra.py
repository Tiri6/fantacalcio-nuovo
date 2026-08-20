"""Rosa di una squadra: contratti, ingaggi, scadenze e stato di conformita'."""

import plotly.express as px
import streamlit as st

from fantacalcio import ui, vista
from fantacalcio.conformita import Momento

ui.intestazione("Rose e contratti", "📋")
ui.barra_laterale()

rose = ui.rose()
nomi = {rosa.squadra.nome: id_ for id_, rosa in rose.items()}
scelta = st.selectbox("Squadra", sorted(nomi))
rosa = rose[nomi[scelta]]

momento = st.radio(
    "Verifica al momento di:",
    options=list(Momento),
    format_func=lambda m: m.value.capitalize(),
    horizontal=True,
    index=2,
)
stato = ui.stati(momento)[nomi[scelta]]

st.caption(
    f"Fantallenatore: {rosa.squadra.fantallenatore} · {ui.badge_esito(stato.conforme)}"
)

colonne = st.columns(5)
colonne[0].metric(
    "Rosa",
    f"{stato.dimensione}/{stato.limite_dimensione}",
    f"{stato.slot_u21} slot U21" if stato.slot_u21 else None,
)
colonne[1].metric(
    "Monte anni",
    f"{stato.anni_impegnati}/{ui.parametri().monte_anni}",
    f"{stato.anni_disponibili} liberi",
)
colonne[2].metric(
    "Contratti annuali", f"{stato.contratti_annuali}/{stato.annuali_richiesti}"
)
colonne[3].metric("Ingaggi", ui.milioni(stato.monte_ingaggi))
colonne[4].metric(
    "Spazio sotto il cap",
    ui.milioni(stato.spazio_salariale),
    f"dead money {ui.milioni(stato.dead_money)}" if stato.dead_money else None,
    delta_color="inverse" if stato.dead_money else "normal",
)

ui.mostra_violazioni(stato.violazioni)

st.divider()
sinistra, destra = st.columns([3, 2])

dettaglio = vista.rosa_dettagliata(rosa, ui.DATA_DRAFT, ui.parametri())

with sinistra:
    st.subheader("Rosa")
    st.dataframe(
        ui.in_milioni(dettaglio),
        hide_index=True,
        use_container_width=True,
        column_config=ui.COLONNE_EURO,
        height=520,
    )

with destra:
    st.subheader("Anni di contratto")
    per_durata = dettaglio.groupby("Anni residui").size().reset_index(name="Giocatori")
    figura = px.bar(
        per_durata,
        x="Anni residui",
        y="Giocatori",
        text="Giocatori",
        labels={"Anni residui": "Anni residui"},
    )
    figura.update_layout(margin={"t": 20, "b": 10, "l": 10, "r": 10})
    st.plotly_chart(figura, use_container_width=True)

    st.subheader("Dove vanno gli ingaggi")
    dettaglio["Fascia"] = dettaglio["Ruoli"].str.split(" / ").str[0]
    per_ruolo = dettaglio.groupby("Fascia", as_index=False)["Ingaggio"].sum()
    torta = px.pie(per_ruolo, names="Fascia", values="Ingaggio", hole=0.45)
    torta.update_traces(textposition="inside", textinfo="percent")
    torta.update_layout(margin={"t": 20, "b": 10, "l": 10, "r": 10})
    st.plotly_chart(torta, use_container_width=True)

    if rosa.dead_money:
        st.subheader("Dead money")
        for voce in rosa.dead_money:
            stato_voce = "addebitato" if voce.addebitato else "da addebitare"
            st.write(f"{voce.nome_giocatore}: {ui.milioni(voce.importo)} ({stato_voce})")
