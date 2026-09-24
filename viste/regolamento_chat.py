"""Chat sul regolamento: si chiede una norma a parole e si riceve la risposta.

La pagina Regolamento mostra le tabelle; questa risponde alle domande che le
tabelle non chiudono ("posso mettere un difensore al posto di un attaccante?",
"quanti annuali mi servono con 32 giocatori?"). La fonte e' la stessa: il
dossier che `assistente.scheda_regolamento` costruisce dai parametri della
lega, non il ricordo che il modello ha di altri fantacalci.

La conversazione vive nel `session_state`, separata per lega: due leghe hanno
regole diverse, e mescolarne le risposte sarebbe peggio che perdere la
cronologia.
"""

import streamlit as st

from fantacalcio import assistente, ui
from fantacalcio.assistente import (
    AssistenteNonConfigurato,
    AssistenteNonRaggiungibile,
    DomandaNonValida,
    Messaggio,
)
from fantacalcio.config import leggi_secret

ui.barra_laterale()

utente = ui.utente_corrente()
lega = ui.lega_corrente()

ui.intestazione(
    "Chat sul regolamento",
    "💬",
    "Chiedi una norma a parole: rispondo con le regole di questa lega.",
)

CHIAVE_STORIA = f"_chat_regolamento_{lega.id}"

DOMANDE_DI_ESEMPIO = (
    "Quanti contratti annuali mi servono con 32 giocatori in rosa?",
    "Chi puo' entrare al posto di un difensore centrale?",
    "Quanto mi costa svincolare un giocatore?",
    "A quanti punti scatta il primo gol?",
)


def _storia() -> list[Messaggio]:
    return st.session_state.setdefault(CHIAVE_STORIA, [])


# --- la chiave ---------------------------------------------------------------
# Senza chiave la pagina non si apre a meta': dice cosa manca e a chi chiederlo.

chiave = leggi_secret(assistente.CHIAVE_SECRET)
if not chiave:
    st.info(
        "**La chat non e' ancora attiva.** Serve una chiave dell'API di "
        "Anthropic: e' l'unico pezzo del sito che non gira da solo.",
        icon="🔌",
    )
    if utente.id == lega.admin_id or utente.puo_importare:
        st.markdown(
            "**Come si attiva** (lo puoi fare tu, sei il presidente):\n\n"
            "1. prendi una chiave su "
            "[console.anthropic.com](https://console.anthropic.com/settings/keys)\n"
            "2. apri la dashboard su [share.streamlit.io](https://share.streamlit.io)"
            " → **⋮** accanto all'app → **Settings** → **Secrets**\n"
            f'3. aggiungi una riga `{assistente.CHIAVE_SECRET} = "sk-ant-..."`\n'
            "4. salva: l'app riparte da sola\n\n"
            "In locale la stessa riga va in `.streamlit/secrets.toml`, che non "
            "finisce su Git."
        )
    else:
        st.caption(
            "Chiedi al presidente della lega di configurarla: gli basta "
            "aggiungere un secret."
        )
    st.page_link("viste/regolamento.py", label="Torna al regolamento", icon="📖")
    st.stop()

# --- il dossier --------------------------------------------------------------
# Si ricostruisce a ogni giro: e' un `join` di stringhe, costa niente, e cosi'
# una regola cambiata in "Impostazioni lega" vale dalla domanda dopo.

scheda = assistente.scheda_regolamento(
    ui.parametri(),
    lega.opzioni,
    nome_lega=lega.nome,
    data_u21=ui.data_u21(),
    punti_aperti=assistente.punti_aperti_del_progetto(),
)

with st.expander("Su cosa rispondo"):
    st.caption(
        "La scheda che leggo e' generata dal gestionale: i parametri del "
        "regolamento, le scelte di questa lega, le tabelle del Mantra e i "
        "punti che la lega non ha ancora votato. Rose, contratti e utenti non "
        "ci sono: la chat parla di regole, non di squadre."
    )
    st.caption(
        "Le domande vengono inviate ad Anthropic per essere elaborate. Non "
        "scriverci dentro niente che non scriveresti in bacheca."
    )
    st.code(scheda, language="markdown")

# --- la conversazione --------------------------------------------------------

if not _storia():
    st.caption("Non sai da dove cominciare? Prova una di queste.")
    for indice, esempio in enumerate(DOMANDE_DI_ESEMPIO):
        if st.button(esempio, key=f"esempio_{indice}", use_container_width=True):
            st.session_state["_domanda_pendente"] = esempio
            st.rerun()

for messaggio in _storia():
    with st.chat_message("user" if messaggio.ruolo == "utente" else "assistant"):
        st.markdown(messaggio.testo)

domanda = st.chat_input(
    "Chiedi una regola…", max_chars=assistente.LIMITE_DOMANDA
) or st.session_state.pop("_domanda_pendente", None)

if domanda:
    try:
        # Si valida prima di disegnare: una domanda vuota non deve comparire
        # nella cronologia come se fosse stata fatta.
        pezzi = assistente.rispondi(
            domanda,
            _storia(),
            scheda,
            assistente.crea_client(chiave),
        )
    except (DomandaNonValida, AssistenteNonConfigurato) as errore:
        st.warning(str(errore), icon="✋")
        st.stop()

    with st.chat_message("user"):
        st.markdown(domanda)

    with st.chat_message("assistant"):
        try:
            with st.spinner("Cerco nel regolamento…"):
                risposta = st.write_stream(pezzi)
        except AssistenteNonRaggiungibile as errore:
            st.error(str(errore), icon="⚠️")
            st.stop()

    # `write_stream` restituisce una stringa quando il flusso e' di stringhe,
    # ma se un giorno tornasse una lista di pezzi `str()` ne salverebbe il
    # repr Python nella cronologia: meglio ricucirla.
    testo = risposta if isinstance(risposta, str) else "".join(map(str, risposta))
    _storia().extend([Messaggio("utente", domanda), Messaggio("assistente", testo)])
    st.rerun()

# --- in fondo ----------------------------------------------------------------

if _storia() and st.button("🧹 Svuota la conversazione"):
    st.session_state.pop(CHIAVE_STORIA, None)
    st.rerun()

st.page_link("viste/regolamento.py", label="Il regolamento in tabella", icon="📖")
