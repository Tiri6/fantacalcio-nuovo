"""Cruscotto della lega: chi e' in regola e chi no, a colpo d'occhio."""

import streamlit as st

from fantacalcio import ui, vista
from fantacalcio.conformita import Momento
from fantacalcio.mercato import stato_mercato

ui.intestazione(
    "Cruscotto della lega",
    "🏠",
    "Contratti, monte anni e vincoli salariali di tutte le squadre.",
)
ui.barra_laterale()

momento = st.segmented_control(
    "Controlla le rose come se fosse:",
    options=list(Momento),
    format_func=lambda m: m.value.capitalize(),
    default=Momento.STAGIONE,
    help=(
        "In stagione lo sforamento del Salary Cap da scambio e' tollerato "
        "(art. 8b) e il Salary Floor non si verifica. A fine asta tutto diventa "
        "vincolante."
    ),
)
momento = momento or Momento.STAGIONE

stati = ui.stati(momento)
partite = ui.calendario()
giornate = ui.giornate_disputate(partite)
mercato = stato_mercato(giornate, ui.CALENDARIO)

non_conformi = [s for s in stati.values() if not s.conforme]
parametri = ui.parametri()

colonne = st.columns(4)
colonne[0].metric("Squadre", len(stati))
colonne[1].metric("Giornate disputate", giornate)
colonne[2].metric(
    "Rose non conformi",
    len(non_conformi),
    delta=None if not non_conformi else f"{len(non_conformi)} da sistemare",
    delta_color="inverse",
)
# Il nome completo della finestra verrebbe troncato dentro una metrica.
colonne[3].metric(
    "Ultima finestra aperta",
    mercato.finestra_piu_recente.value.replace("Finestra ", "").capitalize(),
)

if mercato.trade_deadline_superata:
    st.warning(
        "Trade deadline superata: il mercato e' bloccato fino a fine stagione (art. 5).",
        icon="🔒",
    )

st.divider()
st.subheader("Situazione delle rose")

cruscotto = vista.cruscotto_lega(stati)
st.dataframe(
    ui.in_milioni(cruscotto),
    hide_index=True,
    use_container_width=True,
    column_config=ui.COLONNE_EURO,
)
st.caption(
    f"Monte anni {parametri.monte_anni} · Salary Cap "
    f"{ui.milioni(parametri.salary_cap)} · Salary Floor "
    f"{ui.milioni(parametri.salary_floor)} (fonte ingaggi: Capology)"
)

violazioni = vista.violazioni_lega(stati)
if violazioni.empty:
    st.success("Tutte le rose sono conformi al regolamento.", icon="✅")
else:
    st.subheader(f"Violazioni aperte ({len(violazioni)})")
    st.dataframe(violazioni, hide_index=True, use_container_width=True)
