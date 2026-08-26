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

# --- le scelte di questa lega ----------------------------------------------

lega = ui.lega_corrente()
opzioni = lega.opzioni

st.subheader("Le scelte di questa lega")
st.caption(
    "Decise creando la lega. Valgono insieme al regolamento: dove i numeri "
    "differiscono, comanda quello scelto qui."
)

regole_lega = [
    ("Modalita'", opzioni.modalita.etichetta),
    ("Partecipanti", str(opzioni.partecipanti)),
    ("Formato del campionato", opzioni.formato.etichetta),
    ("Giornate", str(opzioni.giornate_totali)),
    ("Assegnazione dei giocatori", opzioni.tipo_asta.etichetta),
    ("Anni di contratto (massimo)", str(opzioni.anni_contratto_massimi)),
    ("Budget cap annuale", f"{opzioni.budget_cap_milioni:.0f} milioni"),
    (
        "Limiti per ruolo",
        (
            f"{opzioni.rosa_portieri} Por · {opzioni.rosa_difensori} Dif · "
            f"{opzioni.rosa_centrocampisti} Cen · {opzioni.rosa_attaccanti} Att"
            if opzioni.limiti_per_ruolo and opzioni.rosa_totale
            else "nessun limite per ruolo"
        ),
    ),
    (
        "Minimo giocatori italiani",
        str(opzioni.minimo_italiani) if opzioni.minimo_italiani else "nessun vincolo",
    ),
    (
        "Minimo Under 21 italiani",
        str(opzioni.minimo_u21_italiani)
        if opzioni.minimo_u21_italiani
        else "nessun vincolo",
    ),
    (
        "Scambi per stagione",
        "illimitati"
        if opzioni.scambi_illimitati
        else f"{opzioni.scambi_per_stagione} per squadra",
    ),
    (
        "Under 21: data di riferimento",
        ui.data_u21().strftime("%d/%m/%Y"),
    ),
    ("Primo gol", f"{opzioni.soglia_primo_gol:g} punti"),
    ("Gol successivi", f"uno ogni {opzioni.passo_gol:g} punti"),
    (
        "Competizioni",
        " · ".join(f"{c.icona} {c.etichetta}" for c in opzioni.competizioni),
    ),
]

st.dataframe(
    pd.DataFrame(regole_lega, columns=["Regola", "Valore in questa lega"]),
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

if opzioni.supercoppa:
    st.markdown(
        f"**Supercoppa** — {opzioni.regole_supercoppa.criterio.etichetta}, "
        + (
            "si gioca prima dell'inizio del campionato."
            if opzioni.regole_supercoppa.prima_della_stagione
            else "si gioca a stagione in corso."
        )
    )

st.divider()

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
