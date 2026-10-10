"""F1 Rush Finale: la classifica a tappe sulle ultime giornate di Serie A.

Compare solo se la lega la gioca. Ha sostituito la Supercoppa nel V3, e non e'
un cambio di nome: la Supercoppa era una gara fra due squadre, qui corrono
tutte e dieci e si contano i punti di tappa.
"""

import streamlit as st

from fantacalcio import schermate, ui
from fantacalcio.competizioni import (
    CriterioF1Rush,
    TipoCompetizione,
    crea_titolo,
    giornate_f1_rush,
    titolo_esistente,
)
from fantacalcio.data import archivio, prossimo_id, salva_titolo
from fantacalcio.vista import classifica_f1_tabella, tappe_f1

ui.barra_laterale()
schermate.mostra_messaggio()

utente = ui.utente_corrente()
lega = ui.lega_corrente()
regole = lega.opzioni.regole_f1_rush
amministra = utente.id == lega.admin_id or utente.puo_importare

turni = giornate_f1_rush(regole=regole)
ui.intestazione(
    "F1 Rush Finale",
    "🏁",
    f"Ultime {regole.giornate_serie_a} giornate di Serie A "
    f"({turni[0]}ª–{turni[-1]}ª) · {regole.criterio.etichetta}",
)

arch = archivio()
tappe = tappe_f1(arch, regole)

# --- la classifica ----------------------------------------------------------

if not tappe:
    st.info(
        "Nessuna tappa disputata: la classifica compare quando i risultati "
        "delle ultime giornate sono caricati.",
        icon="🏁",
    )
else:
    senza_serie_a = all(t["serie_a"] is None for t in tappe)
    if senza_serie_a:
        st.warning(
            "Il calendario caricato non dice a quale giornata di **Serie A** "
            "corrisponde ogni turno, quindi qui si usano le ultime "
            f"{len(tappe)} giornate di lega disputate "
            f"({tappe[0]['giornata']}ª–{tappe[-1]['giornata']}ª). Compilando "
            "`giornata_serie_a` in fase di import, il conto diventa quello "
            "letterale dell'articolo 1.",
            icon="⚠️",
        )

    st.dataframe(classifica_f1_tabella(arch, regole), hide_index=True, width="stretch")
    st.caption(
        "Ordine: punti, poi vittorie di tappa, poi fantapunti totali — i due "
        "spareggi della Formula 1, nel suo stesso ordine. A pari fantapunti "
        "nella stessa tappa valgono i pari merito, e prendono tutte i punti "
        "della posizione migliore."
    )

    if regole.criterio is CriterioF1Rush.PUNTI_PER_POSIZIONE:
        scala = " · ".join(
            f"{posizione}º = {punti}"
            for posizione, punti in enumerate(regole.punti_per_posizione, start=1)
        )
        st.caption(f"Punti di tappa: {scala}")

    with st.expander("Tappa per tappa"):
        for tappa in tappe:
            ordinata = sorted(tappa["punti"].items(), key=lambda v: -v[1])
            quale = (
                f"{tappa['serie_a']}ª di Serie A"
                if tappa["serie_a"]
                else f"{tappa['giornata']}ª di lega"
            )
            podio = " · ".join(f"{nome} {punti:.1f}" for nome, punti in ordinata[:3])
            st.markdown(f"**{quale}** — {podio}")

st.divider()

# --- vincitrice -------------------------------------------------------------

st.subheader("Vincitrice")

titoli = ui.albo()
gia_vinta = titolo_esistente(titoli, TipoCompetizione.F1_RUSH, lega.stagione)

if gia_vinta:
    st.success(f"F1 Rush {lega.stagione}: **{gia_vinta.squadra_nome}**.", icon="🏁")
elif amministra:
    squadre = ui.squadre()
    nomi = sorted(squadre["nome"]) if not squadre.empty else []
    # In cima c'e' chi guida la classifica: e' quasi sempre la risposta, ma
    # resta una proposta — i risultati possono non essere tutti caricati.
    classifica = classifica_f1_tabella(arch, regole)
    if not classifica.empty:
        prima = classifica.iloc[0]["Squadra"]
        nomi = [prima] + [n for n in nomi if n != prima]
    if nomi:
        vincitrice = st.selectbox("Chi ha vinto", nomi, key="_f1_vincitrice")
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
                        competizione=TipoCompetizione.F1_RUSH,
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
                    f"F1 Rush {lega.stagione} a {vincitrice}.",
                )
                st.rerun()
else:
    st.info("Non ancora assegnata.", icon="🏁")

st.caption("Montepremi: i calzettoni di una squadra di Serie A (art. 1).")
