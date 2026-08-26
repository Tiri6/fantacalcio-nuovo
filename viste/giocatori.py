"""Lista giocatori: tutti quelli tesserabili, con chi li possiede o svincolati."""

import streamlit as st

from fantacalcio import tema, ui
from fantacalcio.regole import ETICHETTE_RUOLO

ui.intestazione(
    "Lista giocatori",
    "👥",
    "Il listone della lega: chi appartiene a una squadra e chi e' svincolato.",
)
ui.barra_laterale()

giocatori = ui.giocatori_con_proprietario()
if giocatori.empty:
    st.info(
        "Il listone non e' ancora stato caricato. Si importa dalla pagina "
        "«Importa dati».",
        icon="📋",
    )
    st.stop()

svincolati = int((giocatori["Squadra"] == ui.SVINCOLATO).sum())
ui.griglia_dati(
    [
        {"etichetta": "Giocatori", "valore": str(len(giocatori))},
        {
            "etichetta": "Tesserati",
            "valore": str(len(giocatori) - svincolati),
            "quota": (len(giocatori) - svincolati) / max(len(giocatori), 1),
        },
        {
            "etichetta": "Svincolati",
            "valore": str(svincolati),
            "nota": "disponibili al draft",
            "stato": "avviso" if svincolati else "ok",
        },
        {
            "etichetta": "Italiani",
            "valore": str(int(giocatori["Ita"].sum())),
            "nota": f"di cui {int(giocatori['U21'].sum())} Under 21",
        },
    ]
)

st.divider()

# --- filtri -----------------------------------------------------------------

riga = st.columns([2, 2, 2, 1, 1])
cerca = riga[0].text_input("Cerca", placeholder="Nome o club")
squadre_scelte = riga[1].multiselect(
    "Squadra", sorted(giocatori["Squadra"].unique()), placeholder="Tutte"
)
ruoli_scelti = riga[2].multiselect(
    "Ruolo",
    sorted({r for elenco in giocatori["Ruoli"] for r in elenco.split("/")}),
    placeholder="Tutti",
    format_func=lambda r: f"{r} — {ETICHETTE_RUOLO.get(r, r)}",
)
solo_italiani = riga[3].toggle("Solo Ita")
solo_u21 = riga[4].toggle("Solo U21")

filtrati = giocatori
if cerca.strip():
    testo = cerca.strip().lower()
    filtrati = filtrati[
        filtrati["Giocatore"].str.lower().str.contains(testo, na=False)
        | filtrati["Club"].str.lower().str.contains(testo, na=False)
    ]
if squadre_scelte:
    filtrati = filtrati[filtrati["Squadra"].isin(squadre_scelte)]
if ruoli_scelti:
    filtrati = filtrati[
        filtrati["Ruoli"].apply(lambda r: any(x in r.split("/") for x in ruoli_scelti))
    ]
if solo_italiani:
    filtrati = filtrati[filtrati["Ita"]]
if solo_u21:
    filtrati = filtrati[filtrati["U21"]]

st.caption(f"{len(filtrati)} giocatori su {len(giocatori)}")
st.dataframe(
    ui.in_milioni(filtrati),
    hide_index=True,
    use_container_width=True,
    column_config={
        **ui.COLONNE_EURO,
        "Ita": st.column_config.CheckboxColumn("🇮🇹", help="Italiano"),
        "U21": st.column_config.CheckboxColumn(
            "U21", help=f"Under 21 al {ui.data_u21().strftime('%d/%m/%Y')}"
        ),
        "Anni": st.column_config.NumberColumn("Anni", help="Anni di contratto residui"),
    },
)

st.caption(
    f"Lo status Under 21 si valuta al **{ui.data_u21().strftime('%d/%m/%Y')}**: "
    "chi compie 21 anni dopo resta Under per tutta la stagione."
)

with st.expander("Legenda dei ruoli Mantra"):
    st.markdown(
        " ".join(
            tema.pastiglia(f"{sigla} · {nome}") for sigla, nome in ETICHETTE_RUOLO.items()
        ),
        unsafe_allow_html=True,
    )
