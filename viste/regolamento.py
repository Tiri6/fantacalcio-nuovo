"""I parametri del regolamento attualmente applicati dal gestionale."""

import pandas as pd
import streamlit as st

from fantacalcio import ui
from fantacalcio.regole import ETICHETTE_RUOLO

ui.intestazione(
    "Regolamento applicato",
    "📖",
    "Questi sono i valori che il gestionale usa per validare rose e scambi.",
)
ui.barra_laterale()

p = ui.parametri()

st.subheader("Composizione rosa (art. 2)")
st.dataframe(
    pd.DataFrame(
        [
            ("Giocatori minimi", p.rosa_minimo),
            ("Giocatori massimi", p.rosa_massimo_base),
            ("Massimo con espansione Under 21", p.rosa_massimo_assoluto),
            ("Portieri massimi", p.portieri_massimo),
            ("Slot Under 21 massimi", p.slot_u21_massimi),
            ("Eta limite Under 21 al draft", p.eta_limite_u21),
            ("Monte anni", p.monte_anni),
            (
                "Anni per contratto",
                f"da {p.contratto_anni_minimo} a {p.contratto_anni_massimo}",
            ),
        ],
        columns=["Voce", "Valore"],
    ),
    hide_index=True,
    use_container_width=True,
)

st.subheader('Regola "1/3": contratti annuali obbligatori')
st.dataframe(
    pd.DataFrame(
        [
            (f"{s.rosa_da}-{s.rosa_a} giocatori", s.minimo_annuali)
            for s in p.soglie_annuali
        ],
        columns=["Dimensione rosa", "Annuali minimi"],
    ),
    hide_index=True,
    use_container_width=True,
)

st.subheader("Economia (art. 4 e 7)")
st.dataframe(
    pd.DataFrame(
        [
            ("Salary Cap", ui.milioni(p.salary_cap)),
            ("Salary Floor", ui.milioni(p.salary_floor)),
            ("Salary Floor attivo", "Si" if p.salary_floor_attivo else "No"),
            ("Dead Money da svincolo", f"{p.quota_dead_money:.0%} del valore residuo"),
            ("Fonte ingaggi", "Capology"),
        ],
        columns=["Voce", "Valore"],
    ),
    hide_index=True,
    use_container_width=True,
)

st.subheader("Mercato e scambi (art. 5, 6 e 8)")
st.dataframe(
    pd.DataFrame(
        [
            ("Giornate per gironcino", p.giornate_per_gironcino),
            (
                "Prolungamenti per squadra a stagione (Lodo Longoni)",
                p.prolungamenti_per_squadra_a_stagione,
            ),
            (
                "Prolungamenti per giocatore in lega (Lodo Corti)",
                p.prolungamenti_per_giocatore_in_lega,
            ),
            ("Preavviso di ratifica di uno scambio", f"{p.ore_ratifica_scambio} ore"),
        ],
        columns=["Voce", "Valore"],
    ),
    hide_index=True,
    use_container_width=True,
)

st.subheader("Punteggio (art. 1)")
st.dataframe(
    pd.DataFrame(
        [
            ("Modalita", "Mantra"),
            ("Fonte voti", "Statistico + Redazione"),
            ("Primo gol a", f"{p.soglia_primo_gol:.0f} punti"),
            ("Poi un gol ogni", f"{p.passo_gol:.0f} punti"),
            (
                "Modificatore di difesa",
                "Attivo" if p.modificatore_difesa else "Disattivo",
            ),
        ],
        columns=["Voce", "Valore"],
    ),
    hide_index=True,
    use_container_width=True,
)

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
