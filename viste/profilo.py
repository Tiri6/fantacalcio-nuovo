"""Il mio profilo: chi sono in questa lega e come cambio la password."""

import streamlit as st

from fantacalcio import schermate, tema, ui

ui.barra_laterale()
schermate.mostra_messaggio()

utente = ui.utente_corrente()
lega = ui.lega_corrente()
credenziali = ui.credenziali_correnti()

ui.intestazione("Il mio profilo", "👤", f"{utente.nome} — {lega.nome}")

squadre = ui.squadre()
nome_squadra = "— nessuna —"
if utente.squadra_id is not None and not squadre.empty:
    sua = squadre[squadre["id"] == utente.squadra_id]
    if not sua.empty:
        nome_squadra = str(sua.iloc[0]["nome"])

ui.griglia_dati(
    [
        {"etichetta": "Nome utente", "valore": utente.nome_utente},
        {"etichetta": "Ruolo", "valore": utente.ruolo.etichetta},
        {"etichetta": "Squadra", "valore": nome_squadra},
    ]
)

if utente.email:
    st.caption(f"Email registrata: {utente.email}")

st.divider()
st.subheader("Cambia la password")
st.caption(
    "Serve conoscere quella attuale. Se l'hai dimenticata, chiedi al "
    "presidente di lega di reimpostarla: ti dara' una password temporanea da "
    "sostituire al primo accesso."
)
schermate.modulo_cambio_password(credenziali)

st.divider()
st.markdown(
    tema.scheda(
        "Perche' non c'e' il recupero via email",
        "Il sito non ha un server di posta, e montarne uno per una lega di "
        "amici non si giustifica. Al suo posto la password la reimposta chi "
        "amministra e te la consegna a voce: e' l'unico punto in cui serve "
        "fidarsi di una persona invece che di un link.",
        icona="✉️",
    ),
    unsafe_allow_html=True,
)
