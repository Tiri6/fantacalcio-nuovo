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


def _spiega_e_fermati(errore: AttributeError) -> None:
    """Trasforma un AttributeError d'avvio in un'istruzione utile.

    Streamlit ricarica questo file e le pagine in `viste/`, ma **non** i moduli
    gia' importati: dopo un aggiornamento `app.py` puo' essere nuovo mentre
    `fantacalcio/` e' ancora quello di prima, e il primo campo o funzione
    aggiunti di recente alzano un AttributeError che uccide il sito.

    Questa funzione vive **qui dentro** e usa solo `streamlit`, di proposito:
    una guardia che stesse in `fantacalcio/ui.py` sarebbe lei stessa parte del
    codice vecchio, e mancherebbe proprio quando serve. E' l'errore che ho gia'
    fatto una volta.
    """
    st.error(
        "**Il sito e' stato aggiornato, ma sta ancora usando il codice "
        "precedente.**\n\n"
        "Succede quando l'applicazione non riparte da zero dopo un "
        "aggiornamento: questa pagina e' quella nuova, i moduli sotto sono "
        "quelli vecchi.",
        icon="🔄",
    )
    st.markdown(
        "**Come si risolve** — riavvia l'applicazione:\n\n"
        "1. apri la dashboard su [share.streamlit.io](https://share.streamlit.io)\n"
        "2. menu **⋮** accanto all'app → **Reboot app**\n"
        "3. riapri il sito dopo una ventina di secondi\n\n"
        "Non si perde niente: i dati stanno su Supabase, non nell'app."
    )
    st.warning(
        "**Se hai gia' riavviato e l'errore resta**, allora non e' un "
        "disallineamento: e' un difetto vero. Manda il dettaglio qui sotto a "
        "chi sviluppa.",
        icon="🐞",
    )
    st.code(f"{type(errore).__name__}: {errore}", language=None)
    st.stop()


# L'avvio sta dentro la guardia: se `fantacalcio` e' la versione vecchia, anche
# `ui.configura_app` potrebbe non esistere ancora.
try:
    from fantacalcio import ui

    ui.configura_app()

    utente = ui.richiedi_login()
    ui.richiedi_password_nuova(utente)
    lega = ui.richiedi_lega(utente)
    ui.richiedi_squadra(utente, lega)

    opzioni = lega.opzioni
    coppa_attiva = opzioni.coppa_italia
    supercoppa_attiva = opzioni.supercoppa
except AttributeError as disallineamento:
    _spiega_e_fermati(disallineamento)
    raise  # non si arriva qui: `_spiega_e_fermati` chiama st.stop()

# --- Lega -------------------------------------------------------------------
# La bacheca e' la pagina d'ingresso: chi entra vuole sapere cosa e' successo,
# non leggere una tabella di contratti.
sezione_lega = [
    st.Page("viste/bacheca.py", title="Bacheca", icon="📣", default=True),
    st.Page("viste/home.py", title="Cruscotto", icon="🏠"),
    # Le due pagine della settimana: si schiera, e poi si guarda la giornata.
    # Stanno in alto perche' sono quelle che si aprono piu' spesso.
    st.Page("viste/formazione.py", title="Formazione", icon="📋"),
    st.Page("viste/giornata.py", title="Giornata", icon="⚔️"),
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
    # Una tabella sola per tutti i giocatori: chi c'e', chi lo possiede e da
    # dove arrivano i dati. Erano due pagine che dicevano quasi la stessa cosa.
    st.Page("viste/listone.py", title="Listone giocatori", icon="📋"),
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
