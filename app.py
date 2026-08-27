"""Punto di ingresso di FantaCalcio NuoVo: configura la pagina e la navigazione.

Prima del menu ci sono quattro cancelli, in quest'ordine: accesso, password
(solo dopo una reimpostazione), lega, squadra. Ognuno ferma la pagina finche'
non e' superato, quindi da qui in giu' si puo' dare per scontato che ci sia un
utente dentro una lega.

Le singole schermate stanno in `viste/`. Si usa `st.navigation` invece della
cartella magica `pages/` per avere etichette in italiano, sezioni, e un menu
che cambia con la lega: le competizioni non attivate non compaiono.
"""

import streamlit as st

from fantacalcio import ui

ui.configura_app()

utente = ui.richiedi_login()
ui.richiedi_password_nuova(utente)
lega = ui.richiedi_lega(utente)
ui.richiedi_squadra(utente, lega)

# Streamlit ricarica `app.py` e le pagine in `viste/`, ma non i moduli gia'
# importati: dopo un aggiornamento questo file puo' essere nuovo mentre
# `fantacalcio/` e' ancora quello di prima, e il primo campo aggiunto di
# recente alza un AttributeError che uccide il sito. Invece di lasciare un
# traceback illeggibile, si spiega che basta riavviare.
try:
    opzioni = lega.opzioni
    coppa_attiva = opzioni.coppa_italia
    supercoppa_attiva = opzioni.supercoppa
except AttributeError as disallineamento:
    ui.spiega_codice_disallineato(disallineamento)
    raise  # non si arriva qui: spiega_codice_disallineato chiama st.stop()

# --- Lega -------------------------------------------------------------------
# La bacheca e' la pagina d'ingresso: chi entra vuole sapere cosa e' successo,
# non leggere una tabella di contratti.
sezione_lega = [
    st.Page("viste/bacheca.py", title="Bacheca", icon="📣", default=True),
    st.Page("viste/home.py", title="Cruscotto", icon="🏠"),
    st.Page("viste/campionato.py", title="Campionato", icon="🏆"),
]

# Coppa e Supercoppa compaiono solo se la lega le gioca: una voce di menu che
# parla di una competizione inesistente e' peggio di una voce mancante.
if coppa_attiva:
    sezione_lega.append(st.Page("viste/coppa.py", title="Coppa Italia", icon="🥇"))
if supercoppa_attiva:
    sezione_lega.append(st.Page("viste/supercoppa.py", title="Supercoppa", icon="🏅"))

sezione_lega += [
    st.Page("viste/calendario.py", title="Calendario", icon="📅"),
    st.Page("viste/albo.py", title="Albo d'oro", icon="🏛️"),
    st.Page("viste/regolamento.py", title="Regolamento", icon="📖"),
]

# --- Squadre e giocatori ----------------------------------------------------
sezione_squadre = [
    st.Page("viste/squadre.py", title="Squadre", icon="🛡️"),
    st.Page("viste/giocatori.py", title="Lista giocatori", icon="👥"),
    st.Page("viste/identita.py", title="Identita' squadre", icon="🎨"),
]

# --- Mercato ----------------------------------------------------------------
sezione_mercato = [
    st.Page("viste/draft.py", title="Draft", icon="🎱"),
    st.Page("viste/scambi.py", title="Scambi", icon="🤝"),
    st.Page("viste/mercato.py", title="Componi scambio", icon="🔁"),
]

# Le assegnazioni riscrivono le rose: le vede solo il presidente (art. 1).
if utente.puo_importare:
    sezione_mercato.insert(
        1, st.Page("viste/assegnazioni.py", title="Assegnazioni", icon="📝")
    )

# --- Impostazioni -----------------------------------------------------------
sezione_impostazioni = [
    st.Page("viste/profilo.py", title="Impostazioni profilo", icon="👤"),
    st.Page("viste/lega.py", title="Impostazioni lega", icon="⚙️"),
]
if utente.puo_importare:
    sezione_impostazioni.insert(
        1, st.Page("viste/importa.py", title="Importa dati", icon="📥")
    )

# `expanded=True` non e' cosmetico: senza, oltre la decina di pagine Streamlit
# nasconde le ultime dietro un "altro" e le voci in fondo sembrano non esistere.
st.navigation(
    {
        # Il nome della lega accanto alla macrovoce: con piu' leghe possibili,
        # dice sempre in quale sei.
        f"Lega · {lega.nome}": sezione_lega,
        "Squadre e giocatori": sezione_squadre,
        "Mercato": sezione_mercato,
        "Impostazioni": sezione_impostazioni,
    },
    expanded=True,
).run()
