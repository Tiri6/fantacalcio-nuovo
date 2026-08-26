"""Supercoppa: la sfida fra i vincitori. Compare solo se la lega la gioca."""

import streamlit as st

from fantacalcio import schermate, tema, ui
from fantacalcio.competizioni import (
    CriterioSupercoppa,
    TipoCompetizione,
    crea_titolo,
    finaliste_supercoppa,
    titolo_esistente,
)
from fantacalcio.data import archivio, prossimo_id, salva_titolo

ui.barra_laterale()
schermate.mostra_messaggio()

utente = ui.utente_corrente()
lega = ui.lega_corrente()
regole = lega.opzioni.regole_supercoppa
amministra = utente.id == lega.admin_id or utente.puo_importare

ui.intestazione("Supercoppa", "🏅", regole.criterio.etichetta)

titoli = ui.albo()
stagioni = sorted({t.stagione for t in titoli}, reverse=True)
stagione_precedente = stagioni[0] if stagioni else ""

campione, sfidante = finaliste_supercoppa(titoli, regole, stagione_precedente)

# --- chi gioca --------------------------------------------------------------

st.subheader("Chi si affronta")

if campione and sfidante:
    st.caption(f"Dedotte dall'albo d'oro della stagione {stagione_precedente}.")
    sinistra, centro, destra = st.columns([2, 1, 2])
    sinistra.markdown(tema.pastiglia(campione), unsafe_allow_html=True)
    centro.markdown("<div style='text-align:center'>contro</div>", unsafe_allow_html=True)
    destra.markdown(tema.pastiglia(sfidante, tema.AZZURRO), unsafe_allow_html=True)
else:
    manuale = regole.criterio is CriterioSupercoppa.MANUALE
    st.info(
        "Le due squadre le scegli tu."
        if manuale
        else "L'albo d'oro non ha ancora i vincitori della stagione scorsa: "
        "il primo anno le due squadre si scelgono a mano. Dall'anno prossimo "
        "compariranno da sole.",
        icon="✍️" if manuale else "🗓️",
    )

    if amministra:
        squadre = ui.squadre()
        nomi = sorted(squadre["nome"]) if not squadre.empty else []
        if nomi:
            riga = st.columns(2)
            una = riga[0].selectbox("Prima finalista", nomi, key="_sc_a")
            altre = [n for n in nomi if n != una]
            due = riga[1].selectbox("Seconda finalista", altre, key="_sc_b")
            st.markdown(
                f"{tema.pastiglia(una)} contro {tema.pastiglia(due, tema.AZZURRO)}",
                unsafe_allow_html=True,
            )
            st.caption(
                "Questa scelta vale per la sfida di quest'anno. Registrando il "
                "vincitore nell'albo d'oro, dall'anno prossimo le finaliste si "
                "ricavano da sole."
            )

st.divider()

# --- vincitore --------------------------------------------------------------

st.subheader("Vincitrice")

gia_vinta = titolo_esistente(titoli, TipoCompetizione.SUPERCOPPA, lega.stagione)
if gia_vinta:
    st.success(f"Supercoppa {lega.stagione}: **{gia_vinta.squadra_nome}**.", icon="🏅")
elif amministra:
    squadre = ui.squadre()
    nomi = sorted(squadre["nome"]) if not squadre.empty else []
    candidate = [n for n in (campione, sfidante) if n] or nomi
    if candidate:
        vincitrice = st.selectbox("Chi ha vinto", candidate, key="_sc_vincitrice")
        if st.button("Registra nell'albo d'oro", type="primary"):
            riga_squadra = (
                squadre[squadre["nome"] == vincitrice] if not squadre.empty else None
            )
            squadra_id = (
                int(riga_squadra.iloc[0]["id"])
                if riga_squadra is not None and not riga_squadra.empty
                else None
            )
            try:
                salva_titolo(
                    archivio(),
                    crea_titolo(
                        id_=prossimo_id(archivio(), "albo"),
                        lega_id=lega.id,
                        competizione=TipoCompetizione.SUPERCOPPA,
                        stagione=lega.stagione,
                        squadra_nome=vincitrice,
                        squadra_id=squadra_id,
                    ),
                )
            except Exception as errore:  # noqa: BLE001 - backend diversi
                st.error(f"Non riesco a registrare: {errore}", icon="⛔")
            else:
                ui.invalida_dati()
                st.session_state[schermate.CHIAVE_MESSAGGIO] = (
                    "success",
                    f"Supercoppa {lega.stagione} a {vincitrice}.",
                )
                st.rerun()
else:
    st.info("Non ancora assegnata.", icon="🏅")

st.caption(
    "Si gioca "
    + (
        "prima dell'inizio del campionato."
        if regole.prima_della_stagione
        else "a stagione in corso."
    )
)
