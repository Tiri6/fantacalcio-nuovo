"""Albo d'oro: chi ha vinto cosa, stagione per stagione."""

import pandas as pd
import streamlit as st

from fantacalcio import schermate, tema, ui
from fantacalcio.competizioni import (
    CompetizioneNonValida,
    TipoCompetizione,
    bacheca_squadre,
    crea_titolo,
    ordina_albo,
    titolo_esistente,
)
from fantacalcio.data import archivio, elimina_titolo, prossimo_id, salva_titolo

ui.barra_laterale()
schermate.mostra_messaggio()

utente = ui.utente_corrente()
lega = ui.lega_corrente()
amministra = utente.id == lega.admin_id or utente.puo_importare

ui.intestazione(
    "Albo d'oro",
    "🏛️",
    f"La storia di {lega.nome}: campionati, coppe e supercoppe.",
)

titoli = ordina_albo(ui.albo())
attive = lega.opzioni.competizioni

# --- registrazione ----------------------------------------------------------

if amministra:
    with st.expander("➕ Registra un titolo", expanded=not titoli):
        st.caption(
            "Si registra a competizione finita. Un titolo gia' presente per "
            "quella stagione viene sostituito: il vincitore e' uno solo."
        )
        riga = st.columns(3)
        competizione = riga[0].selectbox(
            "Competizione",
            attive,
            format_func=lambda c: f"{c.icona} {c.etichetta}",
        )
        stagione = riga[1].text_input("Stagione", value=lega.stagione)

        squadre = ui.squadre()
        nomi = sorted(squadre["nome"]) if not squadre.empty else []
        if not nomi:
            st.warning("Non ci sono squadre da premiare.", icon="🫥")
        else:
            vincitrice = riga[2].selectbox("Vincitrice", nomi)
            note = st.text_input(
                "Nota", placeholder="Vinta all'ultima giornata", max_chars=200
            )

            if st.button("Registra il titolo", type="primary", use_container_width=True):
                esistente = titolo_esistente(titoli, competizione, stagione)
                riga_squadra = squadre[squadre["nome"] == vincitrice].iloc[0]
                try:
                    titolo = crea_titolo(
                        id_=(
                            esistente.id if esistente else prossimo_id(archivio(), "albo")
                        ),
                        lega_id=lega.id,
                        competizione=competizione,
                        stagione=stagione,
                        squadra_nome=vincitrice,
                        squadra_id=int(riga_squadra["id"]),
                        note=note,
                    )
                    salva_titolo(archivio(), titolo)
                except (CompetizioneNonValida, Exception) as errore:  # noqa: BLE001
                    st.error(f"Non riesco a registrare il titolo: {errore}", icon="⛔")
                else:
                    ui.invalida_dati()
                    st.session_state[schermate.CHIAVE_MESSAGGIO] = (
                        "success",
                        f"{titolo.etichetta} a {vincitrice}.",
                    )
                    st.rerun()

st.divider()

if not titoli:
    st.info(
        "L'albo e' vuoto. Si riempie da solo man mano che le competizioni "
        "finiscono e chi amministra registra i vincitori.",
        icon="🏛️",
    )
    st.stop()

# --- bacheca per squadra ----------------------------------------------------

st.subheader("Chi ha vinto di piu'")

conteggio = bacheca_squadre(titoli)
righe = []
for nome, per_competizione in conteggio.items():
    riga = {"Squadra": nome, "Totale": sum(per_competizione.values())}
    for tipo in TipoCompetizione:
        riga[f"{tipo.icona} {tipo.etichetta}"] = per_competizione.get(tipo, 0)
    righe.append(riga)

st.dataframe(
    pd.DataFrame(righe).sort_values("Totale", ascending=False),
    hide_index=True,
    use_container_width=True,
)

st.divider()

# --- storico ----------------------------------------------------------------

st.subheader("Stagione per stagione")

for stagione in sorted({t.stagione for t in titoli}, reverse=True):
    della_stagione = [t for t in titoli if t.stagione == stagione]
    with st.container(border=True):
        st.markdown(f"### {stagione}")
        for titolo in della_stagione:
            colonne = st.columns([3, 1])
            with colonne[0]:
                st.markdown(
                    f"{titolo.competizione.icona} **{titolo.competizione.etichetta}** — "
                    + tema.pastiglia(titolo.squadra_nome),
                    unsafe_allow_html=True,
                )
                if titolo.note:
                    st.caption(titolo.note)
            if amministra and colonne[1].button(
                "Rimuovi", key=f"_albo_{titolo.id}", use_container_width=True
            ):
                try:
                    elimina_titolo(archivio(), titolo.id)
                except Exception as errore:  # noqa: BLE001 - backend diversi
                    st.error(f"Non riesco a rimuovere: {errore}", icon="⛔")
                else:
                    ui.invalida_dati()
                    st.session_state[schermate.CHIAVE_MESSAGGIO] = (
                        "success",
                        f"{titolo.etichetta} rimosso dall'albo.",
                    )
                    st.rerun()
