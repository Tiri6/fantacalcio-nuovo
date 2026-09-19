"""Il mio profilo: chi sono in questa lega e come cambio la password."""

import pandas as pd
import streamlit as st

from fantacalcio import schermate, tema, ui
from fantacalcio.anagrafica import anni_compiuti, scrivi_data_italiana

ui.barra_laterale()
schermate.mostra_messaggio()

utente = ui.utente_corrente()
lega = ui.lega_corrente()
credenziali = ui.credenziali_correnti()

ui.intestazione("Il mio profilo", "👤", f"{utente.nome_completo} — {lega.nome}")

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

st.markdown("**I tuoi dati**")
righe = [
    ("Email", utente.email or "— non registrata —"),
    ("Data di nascita", scrivi_data_italiana(utente.data_nascita) or "—"),
    ("Sesso", utente.sesso.etichetta),
    ("Citta'", utente.citta or "—"),
    ("Squadra del cuore", utente.squadra_preferita or "—"),
]
if utente.data_nascita:
    righe.insert(2, ("Eta'", f"{anni_compiuti(utente.data_nascita)} anni"))

st.dataframe(
    pd.DataFrame(righe, columns=["Campo", "Valore"]),
    hide_index=True,
    use_container_width=True,
)
st.caption(
    "Questi dati li hai scritti iscrivendoti. Per ora si cambiano solo dal "
    "database: se ne hai sbagliato uno, scrivilo al presidente di lega."
)

st.divider()
st.subheader("Cambia la password")
st.caption(
    "Serve conoscere quella attuale. Se l'hai dimenticata, dalla schermata di "
    "accesso c'e' la scheda **Password dimenticata**."
)
schermate.modulo_cambio_password(credenziali)

st.divider()
st.subheader("Codice di recupero")
st.caption(
    "E' la chiave di scorta: se un giorno non ricordi la password, con questo "
    "codice rientri da solo e ne scegli una nuova, senza chiedere niente a "
    "nessuno. Generalo adesso, mentre non serve."
)
schermate.modulo_codice_recupero(credenziali)

st.divider()
st.markdown(
    tema.scheda(
        "Perche' non c'e' il recupero via email",
        "Il sito non ha un server di posta, e montarne uno per una lega di "
        "amici non si giustifica. Al suo posto ci sono due strade: il codice "
        "di recupero qui sopra, che usi da solo, e la richiesta al presidente "
        "dalla schermata di accesso, che gli arriva dentro il sito.",
        icona="✉️",
    ),
    unsafe_allow_html=True,
)
