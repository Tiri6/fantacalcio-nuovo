"""I parametri del regolamento attualmente applicati dal gestionale."""

import pandas as pd
import streamlit as st

from fantacalcio import ui
from fantacalcio.competizioni import giornate_f1_rush
from fantacalcio.leghe import prospetto_regolamento
from fantacalcio.regole import ETICHETTE_RUOLO

ui.intestazione(
    "Regolamento applicato",
    "📖",
    "Questi sono i valori che il gestionale usa per validare rose e scambi.",
)
ui.barra_laterale()

if st.button(
    "💬 Chat AI sul regolamento",
    type="primary",
    use_container_width=True,
    help="Chiedi una norma a parole invece di cercarla nelle tabelle.",
):
    st.switch_page("viste/regolamento_chat.py")

p = ui.parametri()
lega = ui.lega_corrente()
opzioni = lega.opzioni

# I gruppi li costruisce `leghe.prospetto_regolamento`, che e' anche quello
# che legge l'API: scritti qui a mano, un lodo avrebbe aggiornato una pagina
# e lasciato l'altra a dire il numero vecchio.
for gruppo in prospetto_regolamento(p, opzioni, ui.data_u21(), lega):
    st.subheader(gruppo.titolo)
    if gruppo.nota:
        st.caption(gruppo.nota)
    st.dataframe(
        pd.DataFrame(
            [(v.voce, v.valore) for v in gruppo.voci], columns=["Voce", "Valore"]
        ),
        hide_index=True,
        use_container_width=True,
    )

if opzioni.coppa_italia:
    coppa = opzioni.regole_coppa
    st.markdown(
        f"**Coppa Italia** — {coppa.formato.etichetta}, {coppa.squadre_ammesse} "
        f"squadre ammesse, primo turno alla {coppa.prima_giornata}ª giornata e "
        f"poi uno ogni {coppa.ogni_quante_giornate}. "
        + (
            "Teste di serie dalla classifica. "
            if coppa.teste_di_serie
            else "Sorteggio libero. "
        )
        + (
            "A parita', passa chi ha piu' fantapunti."
            if coppa.spareggio_ai_fantapunti
            else "A parita' si ripete la sfida."
        )
    )

if opzioni.f1_rush:
    f1 = opzioni.regole_f1_rush
    turni = giornate_f1_rush(regole=f1)
    st.markdown(
        f"**F1 Rush Finale** — ultime {f1.giornate_serie_a} giornate di Serie A "
        f"({turni[0]}ª–{turni[-1]}ª). {f1.criterio.etichetta}."
    )

st.divider()

st.subheader("Ruoli Mantra")
st.dataframe(
    pd.DataFrame(ETICHETTE_RUOLO.items(), columns=["Sigla", "Ruolo"]),
    hide_index=True,
    use_container_width=True,
)

st.divider()
st.warning(
    "Alcuni punti del regolamento restano da decidere o sono ambigui: sono "
    "elencati in PUNTI_APERTI.md nel repository, con l'ipotesi che il codice "
    "applica oggi.",
    icon="❓",
)
